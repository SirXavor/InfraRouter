package main

import (
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

func applyConfig(cfg *Config) error {
	needNetwork := false
	needDHCP := false
	needOSPF := false

	if cfg.WireGuard != nil {
		if err := applyWireGuard(cfg.WireGuard); err != nil {
			return fmt.Errorf("wireguard: %w", err)
		}
		needNetwork = true
	}
	if cfg.GRE != nil {
		if err := applyGRE(cfg.GRE); err != nil {
			return fmt.Errorf("gre: %w", err)
		}
		needNetwork = true
	}
	if cfg.LAN != nil {
		if err := applyLAN(cfg.LAN); err != nil {
			return fmt.Errorf("lan: %w", err)
		}
		needNetwork = true
	}
	if cfg.PXE != nil {
		if err := applyPXE(cfg.PXE); err != nil {
			return fmt.Errorf("pxe: %w", err)
		}
		needDHCP = true
	}
	if len(cfg.DNS) > 0 {
		if err := applyDNS(cfg.DNS); err != nil {
			return fmt.Errorf("dns: %w", err)
		}
		needDHCP = true
	}
	if len(cfg.NTP) > 0 {
		if err := applyNTP(cfg.NTP); err != nil {
			return fmt.Errorf("ntp: %w", err)
		}
	}
	if cfg.OSPF != nil {
		if err := applyOSPF(cfg.OSPF); err != nil {
			return fmt.Errorf("ospf: %w", err)
		}
		needOSPF = true
	}

	if needNetwork {
		if err := uci("commit", "network"); err != nil {
			return fmt.Errorf("commit network: %w", err)
		}
		run("ifdown", "wgclient")
		run("ifup", "wgclient")
		run("ifdown", "grehub")
		run("ifup", "grehub")
	}
	if needDHCP {
		if err := uci("commit", "dhcp"); err != nil {
			return fmt.Errorf("commit dhcp: %w", err)
		}
		run("/etc/init.d/dnsmasq", "restart")
	}
	if needOSPF {
		restartOSPF()
	}
	return nil
}

// ── Section appliers ──────────────────────────────────────────────────────────

func applyWireGuard(cfg *WireGuardConfig) error {
	cmds := [][]string{
		{"set", "network.wgclient=interface"},
		{"set", "network.wgclient.proto=wireguard"},
		{"set", "network.wgclient.private_key=" + cfg.PrivateKey},
		{"set", "network.wgclient.addresses=" + cfg.Address},
	}
	// Delete existing peer section before re-adding (ignore error if missing)
	uci("delete", "network.@wireguard_wgclient[0]") //nolint
	cmds = append(cmds,
		[]string{"add", "network", "wireguard_wgclient"},
		[]string{"set", "network.@wireguard_wgclient[-1].public_key=" + cfg.PublicKey},
		[]string{"set", "network.@wireguard_wgclient[-1].endpoint_host=" + endpointHost(cfg.Endpoint)},
		[]string{"set", "network.@wireguard_wgclient[-1].endpoint_port=" + endpointPort(cfg.Endpoint)},
		[]string{"set", "network.@wireguard_wgclient[-1].persistent_keepalive=25"},
	)
	for _, ip := range cfg.AllowedIPs {
		cmds = append(cmds, []string{"add_list", "network.@wireguard_wgclient[-1].allowed_ips=" + ip})
	}
	if cfg.PresharedKey != "" {
		cmds = append(cmds, []string{"set", "network.@wireguard_wgclient[-1].preshared_key=" + cfg.PresharedKey})
	}
	for _, c := range cmds {
		if err := uci(c...); err != nil {
			return err
		}
	}
	return nil
}

func applyGRE(cfg *GREConfig) error {
	for _, c := range [][]string{
		{"set", "network.grehub=interface"},
		{"set", "network.grehub.proto=gre"},
		{"set", "network.grehub.ipaddr=" + cfg.LocalIP},
		{"set", "network.grehub.peeraddr=" + cfg.RemoteIP},
		{"set", "network.grehub.tunlink=wgclient"},
	} {
		if err := uci(c...); err != nil {
			return err
		}
	}
	return nil
}

func applyLAN(cfg *LANConfig) error {
	return uci("set", "network.lan.ipaddr="+cfg.IP)
}

func applyPXE(cfg *PXEConfig) error {
	uci("set", "dhcp.@dnsmasq[0].confdir=/etc/dnsmasq.d") //nolint
	content := fmt.Sprintf(
		"dhcp-match=set:efi-x86_64,option:client-arch,7\n"+
			"dhcp-match=set:efi-x86_64,option:client-arch,9\n"+
			"dhcp-match=set:bios,option:client-arch,0\n"+
			"dhcp-boot=tag:efi-x86_64,%s,,%s\n"+
			"dhcp-boot=tag:bios,%s,,%s\n",
		cfg.FileEFI, cfg.TFTPServer,
		cfg.FileBIOS, cfg.TFTPServer,
	)
	return writeFile("/etc/dnsmasq.d/pxe.conf", content)
}

func applyDNS(servers []string) error {
	// Hand DNS servers to DHCP clients via option 6
	uci("delete", "dhcp.lan.dhcp_option") //nolint
	return uci("add_list", "dhcp.lan.dhcp_option=6,"+strings.Join(servers, ","))
}

func applyNTP(servers []string) error {
	uci("delete", "system.ntp.server") //nolint
	for _, s := range servers {
		if err := uci("add_list", "system.ntp.server="+s); err != nil {
			return err
		}
	}
	if err := uci("commit", "system"); err != nil {
		return err
	}
	run("/etc/init.d/sysntpd", "restart")
	return nil
}

func applyOSPF(cfg *OSPFConfig) error {
	var networks strings.Builder
	for _, n := range cfg.Networks {
		fmt.Fprintf(&networks, "  network %s area %s\n", n, cfg.Area)
	}
	content := fmt.Sprintf(
		"hostname ospfd\npassword zebra\nlog syslog\n!\nrouter ospf\n"+
			"  ospf router-id %s\n%s!\nline vty\n!\n",
		cfg.RouterID, networks.String(),
	)
	return writeFile(ospfConfigPath(), content)
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func ospfConfigPath() string {
	if _, err := os.Stat("/etc/frr"); err == nil {
		return "/etc/frr/ospfd.conf"
	}
	return "/etc/quagga/ospfd.conf"
}

func restartOSPF() {
	if _, err := os.Stat("/etc/frr"); err == nil {
		run("/etc/init.d/frr", "restart")
		return
	}
	run("/etc/init.d/quagga", "restart")
}

func uci(args ...string) error {
	if dryRun {
		log.Printf("[dry-run] uci %s", strings.Join(args, " "))
		return nil
	}
	out, err := exec.Command("uci", args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("uci %v: %s", args, strings.TrimSpace(string(out)))
	}
	return nil
}

func run(cmd string, args ...string) {
	if dryRun {
		log.Printf("[dry-run] %s %s", cmd, strings.Join(args, " "))
		return
	}
	out, err := exec.Command(cmd, args...).CombinedOutput()
	if err != nil {
		log.Printf("warning: %s %v: %s", cmd, args, strings.TrimSpace(string(out)))
	}
}

func writeFile(path, content string) error {
	if dryRun {
		log.Printf("[dry-run] write %s (%d bytes)", path, len(content))
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(content), 0644)
}

func endpointHost(ep string) string {
	if i := strings.LastIndex(ep, ":"); i >= 0 {
		return ep[:i]
	}
	return ep
}

func endpointPort(ep string) string {
	if i := strings.LastIndex(ep, ":"); i >= 0 {
		return ep[i+1:]
	}
	return "443"
}
