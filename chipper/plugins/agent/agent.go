package main

import (
	"bytes"
	"os"
	"os/exec"
	"strings"
	"unicode/utf8"

	"github.com/kercre123/wire-pod/chipper/pkg/logger"
	"github.com/kercre123/wire-pod/chipper/pkg/vars"
)

// test of SDK implementation

// var Utterances = []string{"what can you do"}
var Utterances = []string{"*"}
var Name = "Agent Controller"

func Action(transcribedText string, botSerial string, guid string, target string) (string, string) {
	scriptPath := "/Users/sward/src/wire-pod/chipper/plugins/agent/agent.sh"

	logger.Println("agent plugin: " + transcribedText)
	if transcribedText == "" {
		return "intent_imperative_praise", ""
	}

	logger.Println("Making request to OpenAI...")
	cmd := exec.Command("/bin/bash", scriptPath, transcribedText)

	var out bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr

	apiKey := strings.TrimSpace(vars.APIConfig.Knowledge.Key)
	cmd.Env = append(os.Environ(), "OPENAI_VECTOR_API_KEY="+apiKey)

	err := cmd.Run()
	if err != nil {
		errOutput := stderr.Bytes()
		if utf8.Valid(errOutput) {
			logger.Println("Failed to execute script:", err, ", Output:", stderr.String())
		} else {
			logger.Println("Failed to execute script: Output contains invalid UTF-8")
		}
		return "intent_imperative_praise", ""
	}

	apiResponse := strings.TrimSpace(out.String())

	logger.Println("OpenAI response: " + apiResponse)

	return "intent_imperative_praise", ""
}
