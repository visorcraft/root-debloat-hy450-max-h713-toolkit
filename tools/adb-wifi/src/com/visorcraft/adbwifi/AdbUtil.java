package com.visorcraft.adbwifi;

import android.content.ContentResolver;
import android.provider.Settings;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.Enumeration;

final class AdbUtil {
    private AdbUtil() {}

    static void enable(ContentResolver resolver) {
        Settings.Global.putInt(resolver, "adb_enabled", 1);
        Settings.Global.putInt(resolver, "adb_wifi_enabled", 1);
    }

    /** First non-loopback IPv4 on an up interface, or null. */
    static String localIpv4() {
        try {
            Enumeration<NetworkInterface> ifaces = NetworkInterface.getNetworkInterfaces();
            if (ifaces == null) return null;
            while (ifaces.hasMoreElements()) {
                NetworkInterface nif = ifaces.nextElement();
                try {
                    if (!nif.isUp() || nif.isLoopback()) continue;
                } catch (Exception ignored) {
                }
                Enumeration<InetAddress> addrs = nif.getInetAddresses();
                while (addrs.hasMoreElements()) {
                    InetAddress addr = addrs.nextElement();
                    if (!(addr instanceof Inet4Address) || addr.isLoopbackAddress()) continue;
                    return addr.getHostAddress();
                }
            }
            return null;
        } catch (Exception ignored) {
            return null;
        }
    }
}
