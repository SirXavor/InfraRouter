package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
)

type apiClient struct {
	baseURL  string
	deviceID string
	token    string
	http     *http.Client
}

type syncRequest struct {
	AppliedVersion int    `json:"applied_version"`
	Status         string `json:"status"`
}

type syncResponse struct {
	Version int              `json:"version"`
	Config  *json.RawMessage `json:"config"`
}

type statusResponse struct {
	Status string `json:"status"`
}

func newClient(baseURL, deviceID, token string) *apiClient {
	return &apiClient{
		baseURL:  baseURL,
		deviceID: deviceID,
		token:    token,
		http:     &http.Client{},
	}
}

func (c *apiClient) enroll(hostname string) error {
	payload := map[string]string{
		"device_id": c.deviceID,
		"token":     c.token,
		"hostname":  hostname,
	}
	body, _ := json.Marshal(payload)
	resp, err := c.http.Post(c.baseURL+"/devices/enroll", "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("enroll: HTTP %d", resp.StatusCode)
	}
	return nil
}

// isApproved returns (true, nil) when approved, (false, nil) when still pending,
// and (false, err) on network or unexpected errors.
func (c *apiClient) isApproved() (bool, error) {
	req, _ := http.NewRequest("GET", c.baseURL+"/devices/"+c.deviceID+"/status", nil)
	req.Header.Set("Authorization", "Bearer "+c.token)
	resp, err := c.http.Do(req)
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()
	if resp.StatusCode == 403 {
		return false, nil // pending or rejected
	}
	if resp.StatusCode != 200 {
		return false, fmt.Errorf("status: HTTP %d", resp.StatusCode)
	}
	var s statusResponse
	json.NewDecoder(resp.Body).Decode(&s)
	return s.Status == "approved", nil
}

// sync sends the current applied_version and returns (version, config, err).
// config is nil when there is nothing to apply.
// Returns errNotApproved if the device was revoked.
func (c *apiClient) sync(appliedVersion int) (int, *Config, error) {
	body, _ := json.Marshal(syncRequest{AppliedVersion: appliedVersion, Status: "ok"})
	req, _ := http.NewRequest("POST", c.baseURL+"/devices/"+c.deviceID+"/sync", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.token)

	resp, err := c.http.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == 403 {
		return 0, nil, errNotApproved
	}
	if resp.StatusCode != 200 {
		return 0, nil, fmt.Errorf("sync: HTTP %d", resp.StatusCode)
	}

	var sr syncResponse
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		return 0, nil, fmt.Errorf("sync decode: %w", err)
	}
	if sr.Config == nil || string(*sr.Config) == "null" {
		return sr.Version, nil, nil
	}
	var cfg Config
	if err := json.Unmarshal(*sr.Config, &cfg); err != nil {
		return 0, nil, fmt.Errorf("config decode: %w", err)
	}
	return sr.Version, &cfg, nil
}

var errNotApproved = fmt.Errorf("device not approved")
