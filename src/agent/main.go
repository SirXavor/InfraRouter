package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"
)

type SyncRequest struct {
	AppliedVersion int    `json:"applied_version"`
	Status         string `json:"status"`
}

type SyncResponse struct {
	Version int             `json:"version"`
	Config  json.RawMessage `json:"config"`
}

type State struct {
	AppliedVersion int `json:"applied_version"`
}

var (
	apiURL   = mustEnv("INFRAROUTER_URL")
	deviceID = mustEnv("INFRAROUTER_DEVICE_ID")
	token    = mustEnv("INFRAROUTER_TOKEN")
	interval = envInt("INFRAROUTER_SYNC_INTERVAL", 60)
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
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return def
	}
	return n
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

func doSync(state State) (State, error) {
	req := SyncRequest{AppliedVersion: state.AppliedVersion, Status: "ok"}
	body, _ := json.Marshal(req)

	url := fmt.Sprintf("%s/devices/%s/sync", apiURL, deviceID)
	httpReq, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return state, err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return state, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return state, fmt.Errorf("sync returned %d", resp.StatusCode)
	}

	var sr SyncResponse
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		return state, err
	}

	if sr.Config == nil || string(sr.Config) == "null" {
		return state, nil
	}

	log.Printf("new config version %d, applying...", sr.Version)
	if err := applyConfig(sr.Config); err != nil {
		return state, fmt.Errorf("apply failed: %w", err)
	}

	state.AppliedVersion = sr.Version
	saveState(state)
	log.Printf("config version %d applied", sr.Version)
	return state, nil
}

func enroll() error {
	payload := map[string]string{
		"device_id": deviceID,
		"token":     token,
	}
	body, _ := json.Marshal(payload)
	resp, err := http.Post(apiURL+"/devices/enroll", "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("enroll returned %d", resp.StatusCode)
	}
	log.Printf("enrolled as %s", deviceID)
	return nil
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lmsgprefix)
	log.SetPrefix("[infrarouter] ")

	log.Printf("starting, device_id=%s interval=%ds", deviceID, interval)

	if err := enroll(); err != nil {
		log.Printf("enroll failed (will retry): %v", err)
	}

	state := loadState()
	ticker := time.NewTicker(time.Duration(interval) * time.Second)
	defer ticker.Stop()

	// run immediately on start
	for ; ; <-ticker.C {
		if newState, err := doSync(state); err != nil {
			log.Printf("sync error: %v", err)
		} else {
			state = newState
		}
	}
}
