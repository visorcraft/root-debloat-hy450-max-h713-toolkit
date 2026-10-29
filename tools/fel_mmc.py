#!/usr/bin/env python3
# fel_mmc.py - Host-driven eMMC access for the HY450 Max (Allwinner H713)
# through the BROM FEL USB protocol. Talks directly to the SMHC2 controller
# (0x04022000) via FEL MMIO pokes. No code runs on the device beyond the
# BROM FEL handler.
#
# Subcommands:
#   ver                     FEL version handshake (sanity)
#   probe                   dump CCU/PIO/SMHC2 registers (read-only)
#   init                    bring up CCU clock+reset+gate, pins (if needed),
#                           controller, and run eMMC CMD0/1/2/3/7/16
#   read  <lba> <nblk> <f>  read nblk 512B blocks at LBA into file f
#   readtest                init + read first block of env_a and env_b and
#                           byte-compare against backup images
#   restore                 write backup env_a.img -> env_a, env_b.img -> env_b,
#                           then read both back and sha256-verify
#
# Safety: writes are only allowed inside the env_a/env_b LBA ranges.

import os
import struct
import sys
import time

import usb.core
import usb.util

# Directory holding THIS UNIT's own partition dumps (env_a.img/env_b.img for
# the "restore" command). Make the dumps yourself - never use images from
# another unit. Override with the HY450_BACKUP env var.
BACKUP_DIR = os.environ.get("HY450_BACKUP", "backup")

ENV_A_LBA = 204800          # byte 0x6400000
ENV_B_LBA = 205312          # byte 0x6440000
ENV_BLKS = 512              # 256 KiB each

ALLOWED_WRITE = [(ENV_A_LBA, ENV_A_LBA + ENV_BLKS),
                 (ENV_B_LBA, ENV_B_LBA + ENV_BLKS)]

SMHC2 = 0x04022000
CCU = 0x02001000
PIO = 0x02000000

# CCU (H616-style layout inside the 0x2001000..0x2003000 window)
CCU_SMHC2_CLK = CCU + 0x0838
CCU_SMHC_BGR = CCU + 0x084C     # bit2 = SMHC2 gate, bit18 = SMHC2 reset deassert
# PIO port C: sun50iw15 uses a 0x30-byte per-port stride:
# PC_CFG0 = PIO+0x60 (PC0..PC7), PC_CFG1 = PIO+0x64 (PC8..PC11)
PC_CFG0 = PIO + 0x60
PC_CFG1 = PIO + 0x64

# SDXC register offsets from SMHC2 base
GCTRL, CLKCR, TMOUT, WIDTH = 0x00, 0x04, 0x08, 0x0C
BLKSZ, BCNTR, CMDR, CARG = 0x10, 0x14, 0x18, 0x1C
RESP0 = 0x20
IMASK, MISTA, RINTR, STAS = 0x30, 0x34, 0x38, 0x3C
FTRGL, FUNS, HWRST = 0x40, 0x44, 0x78
FIFO = 0x200

# CMDR flag bits
START = 1 << 31
SEND_INIT = 1 << 15
RESP_EXP = 1 << 6
RESP_LONG = 1 << 7
RESP_CRC = 1 << 8
DATA_EXP = 1 << 9
WRITE = 1 << 10
WAIT_PRE_OVER = 1 << 13
UPCLK_ONLY = 1 << 21

# RINTR bits
R_RESP_ERR = 1 << 1
R_CMD_DONE = 1 << 2
R_DATA_OVER = 1 << 3
R_RESP_CRC_ERR = 1 << 6
R_DATA_CRC_ERR = 1 << 7
R_RESP_TIMEOUT = 1 << 8
R_DATA_TIMEOUT = 1 << 9
R_FIFO_ERR = 1 << 11
R_END_BIT_ERR = 1 << 15
R_ERROR_MASK = (R_RESP_ERR | R_RESP_CRC_ERR | R_DATA_CRC_ERR |
                R_RESP_TIMEOUT | R_DATA_TIMEOUT | R_FIFO_ERR | R_END_BIT_ERR)

# STAS bits
S_RXWL = 1 << 0
S_TXWL = 1 << 1
S_FIFO_EMPTY = 1 << 2
S_FIFO_FULL = 1 << 3
S_CARD_BUSY = 1 << 9


class FEL:
    def __init__(self):
        self.dev = usb.core.find(idVendor=0x1F3A, idProduct=0xEFE8)
        if self.dev is None:
            sys.exit("FEL device 1f3a:efe8 not found. Put the projector in "
                     "FEL mode (hold pinhole reset, apply power) and plug the "
                     "male-to-male cable.")
        try:
            self.dev.set_configuration()
        except usb.core.USBError as e:
            sys.exit(f"USB config failed: {e}\nPermission problem? Run: "
                     f"sudo chmod 666 /dev/bus/usb/"
                     f"{self.dev.bus:03d}/{self.dev.address:03d}")
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]
        self.ep_out = usb.util.find_descriptor(
            intf, custom_match=lambda e:
            usb.util.endpoint_direction(e.bEndpointAddress) ==
            usb.util.ENDPOINT_OUT)
        self.ep_in = usb.util.find_descriptor(
            intf, custom_match=lambda e:
            usb.util.endpoint_direction(e.bEndpointAddress) ==
            usb.util.ENDPOINT_IN)

    def _awuc(self, reqtype, length):
        # struct aw_usb_request (packed, 32 bytes)
        req = b"AWUC\0\0\0\0" + struct.pack("<IIHI", length, 0x0C000000,
                                             reqtype, length) + b"\0" * 10
        self.ep_out.write(req, timeout=5000)

    def _awus(self):
        # H713 BROM sends more than requested on small transfers; always
        # read with a 64-byte buffer and truncate.
        resp = self.ep_in.read(64, timeout=5000)
        assert bytes(resp[:4]) == b"AWUS", f"bad response {bytes(resp)!r}"

    def _usb_write(self, data):
        self._awuc(0x12, len(data))
        self.ep_out.write(data, timeout=10000)
        self._awus()

    def _usb_read(self, length):
        self._awuc(0x11, length)
        if length <= 8:
            data = bytes(self.ep_in.read(64, timeout=10000))[:length]
        else:
            data = bytes(self.ep_in.read(length, timeout=10000))
        self._awus()
        return data

    def _fel_request(self, req, addr, length):
        self._usb_write(struct.pack("<IIII", req, addr, length, 0))

    def _fel_status(self):
        self._usb_read(8)

    def version(self):
        self._fel_request(0x001, 0, 0)
        data = self._usb_read(32)
        self._fel_status()
        return data

    def read(self, addr, length):
        self._fel_request(0x103, addr, length)
        data = self._usb_read(length)
        self._fel_status()
        return data

    def write(self, addr, data):
        if not data:
            return
        self._fel_request(0x101, addr, len(data))
        self._usb_write(data)
        self._fel_status()

    def rd32(self, addr):
        return struct.unpack("<I", self.read(addr, 4))[0]

    def resync(self):
        """Recover from an aborted prior session. Try a plain version
        handshake first; only if that fails, complete a possibly dangling
        status read and drain, then re-check."""
        try:
            self.version()
            return
        except (usb.core.USBError, AssertionError):
            pass
        # Maybe the BROM is wedged awaiting the status read of a prior
        # transaction: send that read and consume whatever comes back.
        try:
            self._awuc(0x11, 8)
            self.ep_in.read(64, timeout=800)
            self.ep_in.read(64, timeout=800)
        except usb.core.USBError:
            pass
        for _ in range(8):
            try:
                self.ep_in.read(64, timeout=300)
            except usb.core.USBError:
                break
        self.version()  # raises if still dead

    def wr32(self, addr, val):
        self.write(addr, struct.pack("<I", val & 0xFFFFFFFF))


class MMC:
    def __init__(self, fel):
        self.f = fel
        self.base = SMHC2

    def r(self, off):
        return self.f.rd32(self.base + off)

    def w(self, off, val):
        self.f.wr32(self.base + off, val)

    def poll_reg_clear(self, off, mask, tries=200000):
        for _ in range(tries):
            if not (self.r(off) & mask):
                return True
        return False

    def probe(self):
        f = self.f
        print("== CCU window 0x2001820..0x2001860 ==")
        for a in range(CCU + 0x820, CCU + 0x860, 4):
            print(f"  0x{a:08x}: 0x{f.rd32(a):08x}")
        print("== PIO port C config ==")
        print(f"  PC_CFG0 0x{PC_CFG0:08x}: 0x{f.rd32(PC_CFG0):08x}")
        print(f"  PC_CFG1 0x{PC_CFG1:08x}: 0x{f.rd32(PC_CFG1):08x}")
        print("== SMHC2 regs ==")
        for off in (GCTRL, CLKCR, TMOUT, WIDTH, STAS, FTRGL, FUNS, HWRST):
            print(f"  +0x{off:02x}: 0x{self.r(off):08x}")

    def ccu_up(self):
        """Enable SMHC2 module clock (OSC24M/60 = 400 kHz) and deassert reset."""
        f = self.f
        # clock reg: bit31 enable, src=OSC24M (0<<24), N=2 (<<8), M=14
        f.wr32(CCU_SMHC2_CLK, 0x80000000 | (0 << 24) | (2 << 8) | 14)
        # bus gate + reset deassert for SMHC2
        cur = f.rd32(CCU_SMHC_BGR)
        f.wr32(CCU_SMHC_BGR, cur | (1 << 2) | (1 << 18))
        time.sleep(0.005)

    def pins_up(self, mux=2):
        """Mux PC0..PC11 to sdc2. Each pin is a 4-bit field, 8 pins per reg."""
        f = self.f
        v = 0
        for _ in range(8):
            v = (v << 4) | mux
        f.wr32(PC_CFG0, v)               # PC0..PC7
        cur = f.rd32(PC_CFG1)
        cur &= 0xFFFF0000                # keep PC12..PC15
        cur |= v & 0xFFFF                # PC8..PC11 -> mux
        f.wr32(PC_CFG1, cur)

    def controller_up(self):
        # hardware reset of the controller block
        self.w(GCTRL, 0x7)
        if not self.poll_reg_clear(GCTRL, 0x7):
            raise RuntimeError("SMHC2 soft reset timeout")
        self.w(FTRGL, 0x20070008)
        self.w(TMOUT, 0xFFFFFFFF)
        self.w(RINTR, 0xFFFFFFFF)
        self.w(FUNS, 0xCEAA << 16)
        # PIO FIFO access goes through the AHB path on this controller
        self.w(GCTRL, self.r(GCTRL) | (1 << 31))
        # card clock on (CLKCR bit16), then push the clock update
        self.w(CLKCR, 1 << 16)
        self.w(CMDR, START | UPCLK_ONLY | WAIT_PRE_OVER)
        if not self.poll_reg_clear(CMDR, START):
            raise RuntimeError("clock update (UPCLK_ONLY) timeout")
        self.w(RINTR, self.r(RINTR))
        self.w(WIDTH, 0)  # 1-bit bus

    def wait_idle(self, tries=200000):
        """Wait until the card and the controller data FSM are idle."""
        for _ in range(tries):
            st = self.r(STAS)
            if not (st & S_CARD_BUSY) and not (st & (1 << 10)):
                return
        raise RuntimeError("SMHC2/card never idle")

    def cmd(self, idx, arg, flags, long_resp=False):
        self.w(CARG, arg)
        self.w(CMDR, START | flags | (idx & 0x3F))
        for _ in range(200000):
            ri = self.r(RINTR)
            if ri & (R_CMD_DONE | R_ERROR_MASK):
                break
        else:
            raise RuntimeError(f"CMD{idx}: poll timeout (RINTR stuck)")
        if ri & R_ERROR_MASK:
            self.w(RINTR, 0xFFFFFFFF)
            raise RuntimeError(f"CMD{idx}: error RINTR=0x{ri:08x}")
        self.w(RINTR, 0xFFFFFFFF)
        if flags & RESP_EXP:
            if long_resp:
                return [self.r(RESP0 + 4 * i) for i in range(4)]
            return self.r(RESP0)
        return None

    def emmc_init(self):
        # CMD0 go idle (with init sequence)
        self.w(CMDR, START | SEND_INIT | 0)
        if not self.poll_reg_clear(CMDR, START):
            raise RuntimeError("CMD0 timeout")
        self.w(RINTR, 0xFFFFFFFF)
        # CMD1 send OCR until busy bit set
        ocr = 0
        for _ in range(2000):
            ocr = self.cmd(1, 0x40FF8080, RESP_EXP)
            if ocr & (1 << 31):
                break
            time.sleep(0.002)
        else:
            raise RuntimeError("CMD1 never ready")
        sector_mode = bool(ocr & (1 << 30))
        cid = self.cmd(2, 0, RESP_EXP | RESP_LONG, long_resp=True)
        self.cmd(3, 1 << 16, RESP_EXP | RESP_CRC)      # set RCA=1
        self.cmd(7, 1 << 16, RESP_EXP | RESP_CRC)      # select
        self.cmd(16, 512, RESP_EXP | RESP_CRC)         # block len
        return {"ocr": ocr, "sector_mode": sector_mode, "cid": cid}

    def read_block(self, lba):
        self.wait_idle()
        self.w(RINTR, 0xFFFFFFFF)
        self.w(BLKSZ, 512)
        self.w(BCNTR, 512)
        self.w(CARG, lba)
        self.w(CMDR, START | RESP_EXP | RESP_CRC | DATA_EXP |
               WAIT_PRE_OVER | 17)
        out = bytearray()
        # PIO read: 128 words from the FIFO
        for _ in range(128):
            for _ in range(100000):
                st = self.r(STAS)
                if not (st & S_FIFO_EMPTY):
                    break
            else:
                raise RuntimeError(f"read_block LBA {lba}: FIFO starved")
            out += struct.pack("<I", self.r(FIFO))
        for _ in range(200000):
            ri = self.r(RINTR)
            if ri & (R_DATA_OVER | R_ERROR_MASK):
                break
        else:
            raise RuntimeError(f"read_block LBA {lba}: no DATA_OVER")
        if ri & R_ERROR_MASK:
            self.w(RINTR, 0xFFFFFFFF)
            raise RuntimeError(f"read_block LBA {lba}: RINTR=0x{ri:08x}")
        self.w(RINTR, 0xFFFFFFFF)
        self.wait_idle()
        return bytes(out)

    def write_block(self, lba, data):
        assert len(data) == 512
        for lo, hi in ALLOWED_WRITE:
            if lo <= lba < hi:
                break
        else:
            raise RuntimeError(f"write to LBA {lba} outside allowed ranges")
        self.wait_idle()
        self.w(RINTR, 0xFFFFFFFF)
        self.w(BLKSZ, 512)
        self.w(BCNTR, 512)
        self.w(CARG, lba)
        self.w(CMDR, START | RESP_EXP | RESP_CRC | DATA_EXP | WRITE |
               WAIT_PRE_OVER | 24)
        for i in range(128):
            for _ in range(100000):
                st = self.r(STAS)
                if not (st & S_FIFO_FULL):
                    break
            else:
                raise RuntimeError(f"write_block LBA {lba}: FIFO jammed")
            self.w(FIFO, struct.unpack_from("<I", data, i * 4)[0])
        for _ in range(200000):
            ri = self.r(RINTR)
            if ri & (R_DATA_OVER | R_ERROR_MASK):
                break
        else:
            raise RuntimeError(f"write_block LBA {lba}: no DATA_OVER")
        if ri & R_ERROR_MASK:
            self.w(RINTR, 0xFFFFFFFF)
            raise RuntimeError(f"write_block LBA {lba}: RINTR=0x{ri:08x}")
        self.w(RINTR, 0xFFFFFFFF)
        # wait for the card to finish programming
        self.wait_idle()


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    fel = FEL()
    fel.resync()
    mmc = MMC(fel)
    cmd = args[0]

    if cmd == "ver":
        v = fel.version()
        print(" ".join(f"{b:02x}" for b in v))
        return
    if cmd == "probe":
        mmc.probe()
        return

    def bringup():
        mmc.ccu_up()
        mmc.pins_up()
        mmc.controller_up()
        info = mmc.emmc_init()
        print(f"eMMC up: OCR=0x{info['ocr']:08x} "
              f"sector_mode={info['sector_mode']}")

    if cmd == "init":
        bringup()
        return
    if cmd == "read":
        lba, nblk, path = int(args[1], 0), int(args[2], 0), args[3]
        bringup()
        with open(path, "wb") as fh:
            for i in range(nblk):
                fh.write(mmc.read_block(lba + i))
                if (i + 1) % 64 == 0:
                    print(f"  {i + 1}/{nblk} blocks", flush=True)
        print(f"read {nblk} blocks at LBA {lba} -> {path}")
        return
    if cmd == "readtest":
        bringup()
        for name, lba in (("env_a", ENV_A_LBA), ("env_b", ENV_B_LBA)):
            got = mmc.read_block(lba)
            want = open(f"{BACKUP_DIR}/{name}.img", "rb").read(512)
            ok = got == want
            print(f"{name} block0: {'MATCH' if ok else 'MISMATCH'}")
            if not ok:
                print("  got :", got[:64].hex())
                print("  want:", want[:64].hex())
                sys.exit(1)
        print("readtest OK - chain (clocks/pins/protocol/addressing) validated")
        return
    if cmd == "restore":
        bringup()
        for name, lba in (("env_a", ENV_A_LBA), ("env_b", ENV_B_LBA)):
            img = open(f"{BACKUP_DIR}/{name}.img", "rb").read()
            assert len(img) == ENV_BLKS * 512
            print(f"writing {name} ({len(img)} bytes, LBA {lba})...")
            for i in range(ENV_BLKS):
                mmc.write_block(lba + i, img[i * 512:(i + 1) * 512])
                if (i + 1) % 32 == 0:
                    print(f"  wrote {i + 1}/{ENV_BLKS}", flush=True)
        print("verifying readback...")
        import hashlib
        for name, lba in (("env_a", ENV_A_LBA), ("env_b", ENV_B_LBA)):
            h = hashlib.sha256()
            for i in range(ENV_BLKS):
                h.update(mmc.read_block(lba + i))
                if (i + 1) % 64 == 0:
                    print(f"  {name} verify {i + 1}/{ENV_BLKS}", flush=True)
            want = hashlib.sha256(
                open(f"{BACKUP_DIR}/{name}.img", "rb").read()).hexdigest()
            got = h.hexdigest()
            print(f"{name}: {'MATCH' if got == want else 'MISMATCH'}")
            print(f"  got  {got}\n  want {want}")
            if got != want:
                sys.exit(1)
        print("restore complete and verified")
        return
    sys.exit(f"unknown subcommand {cmd!r}")


if __name__ == "__main__":
    main()
