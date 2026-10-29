/* qw daemon client - OEM fifo variant of the koush superuser protocol.
 * Wire format (from disassembly of qw daemon_accept @ 0x1fe70):
 *   int pid            (used for fifo names)
 *   int tty_flag       (0 = no pty; nonzero = daemon allocates /dev/ptmx)
 *   int uid            (overridden by SO_PEERCRED when non-root)
 *   int pid2
 *   int mount_storage
 *   int argc           (<=512) then argc strings (len<=0x1000, len-prefixed)
 * Daemon then mkfifos /dev/com.koushikdutta.superuser.daemon/<pid>.{stdin,stdout,stderr},
 * chowns to our uid, writes ack int(1), opens the fifos (we must open the other ends),
 * reads one more int (ready), forks, child runs su_main with our argv.
 * Command output comes back via the fifos; exit code arrives on the socket.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/select.h>
#include <sys/stat.h>

static int read_full(int fd, void *buf, size_t len) {
    size_t off = 0;
    while (off < len) {
        ssize_t r = read(fd, (char *)buf + off, len - off);
        if (r <= 0) return -1;
        off += (size_t)r;
    }
    return 0;
}
static void write_int(int fd, int val) {
    if (write(fd, &val, sizeof(val)) != (ssize_t)sizeof(val)) {
        fprintf(stderr, "write_int: %s\n", strerror(errno));
        _exit(1);
    }
}
static int read_int_tag(int fd, const char *tag) {
    int v;
    if (read_full(fd, &v, sizeof(v))) {
        fprintf(stderr, "read_int(%s) failed: %s\n", tag, strerror(errno));
        _exit(1);
    }
    return v;
}
static void write_string(int fd, const char *s) {
    int len = (int)strlen(s);
    write_int(fd, len);
    if (len && write(fd, s, len) != (ssize_t)len) {
        fprintf(stderr, "write_string: %s\n", strerror(errno));
        _exit(1);
    }
}

int main(int argc, char **argv) {
    /* daemon may inspect /proc/<pid>/cmdline; look like the vendor client */
    if (strcmp(argv[0], "/system/bin/qw") != 0) {
        char **na = malloc(sizeof(char *) * (argc + 1));
        na[0] = (char *)"/system/bin/qw";
        for (int i = 1; i < argc; i++) na[i] = argv[i];
        na[argc] = NULL;
        execv("/proc/self/exe", na);
        _exit(1);
    }

    int s = socket(AF_LOCAL, SOCK_STREAM, 0);
    struct sockaddr_un sun;
    memset(&sun, 0, sizeof(sun));
    sun.sun_family = AF_LOCAL;
    snprintf(sun.sun_path, sizeof(sun.sun_path), "%s",
             "/dev/com.koushikdutta.superuser.daemon/server");
    if (connect(s, (struct sockaddr *)&sun, sizeof(sun)) != 0) {
        fprintf(stderr, "qwc: connect: %s\n", strerror(errno));
        return 1;
    }

    int pid = getpid();
    write_int(s, pid);
    write_int(s, 0);            /* tty flag = 0: fifos, no pty */
    write_int(s, getuid());
    write_int(s, getppid());
    write_int(s, 0);            /* mount_storage */
    write_int(s, argc);         /* argv[0] "su" + our args */
    write_string(s, "su");
    for (int i = 1; i < argc; i++) write_string(s, argv[i]);

    int ack = read_int_tag(s, "ack");
    fprintf(stderr, "qwc: ack=%d\n", ack);

    char base[300];
    snprintf(base, sizeof(base), "/dev/com.koushikdutta.superuser.daemon/%d", pid);
    char p_in[320], p_out[320], p_err[320];
    snprintf(p_in, sizeof(p_in), "%s.stdin", base);
    snprintf(p_out, sizeof(p_out), "%s.stdout", base);
    snprintf(p_err, sizeof(p_err), "%s.stderr", base);

    /* wait briefly for fifos to appear, then open O_RDWR|O_NONBLOCK (never blocks) */
    int fd_in = -1, fd_out = -1, fd_err = -1;
    for (int tries = 0; tries < 100 && (fd_in < 0 || fd_out < 0 || fd_err < 0); tries++) {
        if (fd_in < 0) fd_in = open(p_in, O_RDWR | O_NONBLOCK);
        if (fd_out < 0) fd_out = open(p_out, O_RDWR | O_NONBLOCK);
        if (fd_err < 0) fd_err = open(p_err, O_RDWR | O_NONBLOCK);
        if (fd_in < 0 || fd_out < 0 || fd_err < 0) usleep(20000);
    }
    if (fd_in < 0 || fd_out < 0 || fd_err < 0) {
        fprintf(stderr, "qwc: fifo open failed: %s\n", strerror(errno));
        return 1;
    }

    write_int(s, 0);            /* ready */

    /* pump: stdin(0) -> fd_in; fd_out -> stdout(1); fd_err -> stderr(2);
     * exit code int from socket ends the session. */
    char buf[4096];
    int code = -100;
    int out_open = 1, err_open = 1;
    for (;;) {
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(s, &rfds);
        int maxfd = s;
        if (out_open) { FD_SET(fd_out, &rfds); if (fd_out > maxfd) maxfd = fd_out; }
        if (err_open) { FD_SET(fd_err, &rfds); if (fd_err > maxfd) maxfd = fd_err; }
        if (select(maxfd + 1, &rfds, NULL, NULL, NULL) < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (FD_ISSET(s, &rfds)) {
            int v;
            if (read_full(s, &v, sizeof(v)) == 0) { code = v; break; }
            break; /* socket closed */
        }
        if (out_open && FD_ISSET(fd_out, &rfds)) {
            ssize_t r = read(fd_out, buf, sizeof(buf));
            if (r > 0) { if (write(1, buf, r) < 0) {} }
            else if (r == 0) out_open = 0;
        }
        if (err_open && FD_ISSET(fd_err, &rfds)) {
            ssize_t r = read(fd_err, buf, sizeof(buf));
            if (r > 0) { if (write(2, buf, r) < 0) {} }
            else if (r == 0) err_open = 0;
        }
    }
    close(s);
    close(fd_in);
    close(fd_out);
    close(fd_err);
    fprintf(stderr, "qwc: exit=%d\n", code);
    return code < 0 ? 1 : code;
}
