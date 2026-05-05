package main

type Config struct {
	WireGuard *WireGuardConfig `json:"wireguard,omitempty"`
	GRE       *GREConfig       `json:"gre,omitempty"`
	OSPF      *OSPFConfig      `json:"ospf,omitempty"`
	LAN       *LANConfig       `json:"lan,omitempty"`
	PXE       *PXEConfig       `json:"pxe,omitempty"`
	DNS       []string         `json:"dns,omitempty"`
	NTP       []string         `json:"ntp,omitempty"`
}

type WireGuardConfig struct {
	PrivateKey   string   `json:"private_key"`
	Address      string   `json:"address"`
	Endpoint     string   `json:"endpoint"`
	PublicKey    string   `json:"public_key"`
	PresharedKey string   `json:"preshared_key,omitempty"`
	AllowedIPs   []string `json:"allowed_ips"`
}

type GREConfig struct {
	LocalIP  string `json:"local_ip"`
	RemoteIP string `json:"remote_ip"`
	Network  string `json:"network"`
}

type OSPFConfig struct {
	RouterID string   `json:"router_id"`
	Area     string   `json:"area"`
	Networks []string `json:"networks"`
}

type LANConfig struct {
	Network string `json:"network"`
	IP      string `json:"ip"`
}

type PXEConfig struct {
	TFTPServer string `json:"tftp_server"`
	FileBIOS   string `json:"file_bios"`
	FileEFI    string `json:"file_efi"`
}
