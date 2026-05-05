package main

import (
	"encoding/json"
	"fmt"
	"os/exec"
)

type Config struct {
	WireGuard *WireGuardConfig `json:"wireguard,omitempty"`
	GRE       *GREConfig       `json:"gre,omitempty"`
	OSPF      *OSPFConfig      `json:"ospf,omitempty"`
	LAN       *LANConfig       `json:"lan,omitempty"`
	PXE       *PXEConfig       `json:"pxe,omitempty"`
}

type WireGuardConfig struct {
	PrivateKey string `json:"private_key"`
	Address    string `json:"address"`   // e.g. 192.168.254.2/32
	Endpoint   string `json:"endpoint"`  // e.g. wg.example.com:443
	PublicKey  string `json:"public_key"` // hub public key
	PresharedKey string `json:"preshared_key,omitempty"`
	AllowedIPs []string `json:"allowed_ips"`
}

type GREConfig struct {
	LocalIP  string `json:"local_ip"`  // e.g. 10.0.2.2
	RemoteIP string `json:"remote_ip"` // e.g. 10.0.2.1 (hub)
	TunnelIP string `json:"tunnel_ip"` // e.g. 192.168.254.2 (wg local IP used as GRE outer src)
}

type OSPFConfig struct {
	RouterID string   `json:"router_id"`
	Area     string   `json:"area"`
	Networks []string `json:"networks"`
}

type LANConfig struct {
	Network string `json:"network"` // e.g. 192.168.2.0/24
	IP      string `json:"ip"`      // e.g. 192.168.2.1
}

type PXEConfig struct {
	TFTPServer  string `json:"tftp_server"`
	FileBIOS    string `json:"file_bios"`
	FileEFI     string `json:"file_efi"`
}

func applyConfig(raw json.RawMessage) error {
	var cfg Config
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return fmt.Errorf("parse config: %w", err)
	}

	if cfg.WireGuard != nil {
		if err := applyWireGuard(cfg.WireGuard); err != nil {
			return fmt.Errorf("wireguard: %w", err)
		}
	}
	if cfg.GRE != nil {
		if err := applyGRE(cfg.GRE); err != nil {
			return fmt.Errorf("gre: %w", err)
		}
	}
	if cfg.LAN != nil {
		if err := applyLAN(cfg.LAN); err != nil {
			return fmt.Errorf("lan: %w", err)
		}
	}
	if cfg.PXE != nil {
		if err := applyPXE(cfg.PXE); err != nil {
			return fmt.Errorf("pxe: %w", err)
		}
	}

	return uci("commit")
}

func applyWireGuard(cfg *WireGuardConfig) error {
	cmds := [][]string{
		{"set", "network.wgclient=interface"},
		{"set", "network.wgclient.proto=wireguard"},
		{"set", "network.wgclient.private_key=" + cfg.PrivateKey},
		{"set", "network.wgclient.addresses=" + cfg.Address},
		{"delete", "network.@wireguard_wgclient[0]"},
		{"add", "network", "wireguard_wgclient"},
		{"set", "network.@wireguard_wgclient[-1].public_key=" + cfg.PublicKey},
		{"set", "network.@wireguard_wgclient[-1].endpoint_host=" + endpointHost(cfg.Endpoint)},
		{"set", "network.@wireguard_wgclient[-1].endpoint_port=" + endpointPort(cfg.Endpoint)},
		{"set", "network.@wireguard_wgclient[-1].persistent_keepalive=25"},
	}
	for _, ip := range cfg.AllowedIPs {
		cmds = append(cmds, []string{"add_list", "network.@wireguard_wgclient[-1].allowed_ips=" + ip})
	}
	if cfg.PresharedKey != "" {
		cmds = append(cmds, []string{"set", "network.@wireguard_wgclient[-1].preshared_key=" + cfg.PresharedKey})
	}
	for _, c := range cmds {
		if err := uci(c...); err != nil && c[0] != "delete" {
			return err
		}
	}
	return nil
}

func applyGRE(cfg *GREConfig) error {
	cmds := [][]string{
		{"set", "network.grehub=interface"},
		{"set", "network.grehub.proto=gre"},
		{"set", "network.grehub.ipaddr=" + cfg.LocalIP},
		{"set", "network.grehub.peeraddr=" + cfg.RemoteIP},
		{"set", "network.grehub.tunlink=wgclient"},
	}
	for _, c := range cmds {
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
	cmds := [][]string{
		{"set", "dhcp.@dnsmasq[0].confdir=/etc/dnsmasq.d"},
	}
	for _, c := range cmds {
		uci(c...)
	}
	pxeConf := fmt.Sprintf(
		"dhcp-match=set:efi-x86_64,option:client-arch,7\n"+
			"dhcp-match=set:efi-x86_64,option:client-arch,9\n"+
			"dhcp-match=set:bios,option:client-arch,0\n"+
			"dhcp-boot=tag:efi-x86_64,%s,,%s\n"+
			"dhcp-boot=tag:bios,%s,,%s\n",
		cfg.FileEFI, cfg.TFTPServer,
		cfg.FileBIOS, cfg.TFTPServer,
	)
	return writeFile("/etc/dnsmasq.d/pxe.conf", pxeConf)
}

func uci(args ...string) error {
	out, err := exec.Command("uci", args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("uci %v: %s", args, out)
	}
	return nil
}

func writeFile(path, content string) error {
	return exec.Command("sh", "-c", fmt.Sprintf("mkdir -p $(dirname %s) && cat > %s << 'HEREDOC'\n%sHEREDOC", path, path, content)).Run()
}

func endpointHost(ep string) string {
	for i := len(ep) - 1; i >= 0; i-- {
		if ep[i] == ':' {
			return ep[:i]
		}
	}
	return ep
}

func endpointPort(ep string) string {
	for i := len(ep) - 1; i >= 0; i-- {
		if ep[i] == ':' {
			return ep[i+1:]
		}
	}
	return "443"
}
