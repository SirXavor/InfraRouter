package main

import (
	"encoding/json"
	"errors"
	"log"
	"os"
	"strconv"
	"time"
)

type State struct {
	AppliedVersion int `json:"applied_version"`
}

var (
	apiURL    = mustEnv("INFRAROUTER_URL")
	deviceID  = mustEnv("INFRAROUTER_DEVICE_ID")
	token     = mustEnv("INFRAROUTER_TOKEN")
	interval  = envInt("INFRAROUTER_SYNC_INTERVAL", 60)
	dryRun    = os.Getenv("INFRAROUTER_DRY_RUN") == "1"
	stateFile = "/etc/infrarouter/state.json"
)

func mustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		log.Fatalf("required env var %s not set", key)
	}
	return v
}

func envInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func loadState() State {
	data, err := os.ReadFile(stateFile)
	if err != nil {
		return State{}
	}
	var s State
	json.Unmarshal(data, &s)
	return s
}

func saveState(s State) {
	os.MkdirAll("/etc/infrarouter", 0700)
	data, _ := json.Marshal(s)
	os.WriteFile(stateFile, data, 0600)
}

func hostname() string {
	h, _ := os.Hostname()
	return h
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lmsgprefix)
	log.SetPrefix("[infrarouter] ")

	if dryRun {
		log.Printf("DRY-RUN mode: UCI commands will be logged but not executed")
	}
	log.Printf("starting device_id=%s interval=%ds", deviceID, interval)

	client := newClient(apiURL, deviceID, token)

	// Phase 1: enroll with exponential backoff
	for backoff := 5; ; backoff = min(backoff*2, 300) {
		if err := client.enroll(hostname()); err != nil {
			log.Printf("enroll failed, retry in %ds: %v", backoff, err)
			time.Sleep(time.Duration(backoff) * time.Second)
			continue
		}
		log.Printf("enrolled, waiting for operator approval...")
		break
	}

	// Phase 2: wait for approval
	for {
		approved, err := client.isApproved()
		if err != nil {
			log.Printf("status check failed: %v", err)
		} else if approved {
			log.Printf("device approved, starting sync loop")
			break
		}
		time.Sleep(30 * time.Second)
	}

	// Phase 3: sync loop
	state := loadState()
	ticker := time.NewTicker(time.Duration(interval) * time.Second)
	defer ticker.Stop()

	for ; ; <-ticker.C {
		version, cfg, err := client.sync(state.AppliedVersion)
		if err != nil {
			if errors.Is(err, errNotApproved) {
				log.Printf("device revoked, re-enrolling...")
				main() // restart from enrollment
				return
			}
			log.Printf("sync error: %v", err)
			continue
		}

		if cfg == nil {
			continue // already up to date
		}

		log.Printf("new config version %d, applying...", version)
		if err := applyConfig(cfg); err != nil {
			log.Printf("apply failed: %v", err)
			// Report error on next sync
			client.sync(state.AppliedVersion) // heartbeat with old version
			continue
		}

		state.AppliedVersion = version
		saveState(state)
		log.Printf("config version %d applied OK", version)
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
