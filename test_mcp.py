import subprocess
import json
import time
import sys

def send_request(process, request_dict):
    """Sends a JSON-RPC request to the MCP server process."""
    req_str = json.dumps(request_dict) + "\n"
    print(f"\n---> Sending Request:\n{json.dumps(request_dict, indent=2)}")
    process.stdin.write(req_str)
    process.stdin.flush()

def read_response(process):
    """Reads a JSON-RPC response from the MCP server process stdout."""
    # Since we are using readline, this blocks until a newline is received
    line = process.stdout.readline()
    if not line:
        return None
    try:
        resp = json.loads(line)
        print(f"<--- Received Response:\n{json.dumps(resp, indent=2)}")
        return resp
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {line}")
        return None

def main():
    print("==================================================")
    print("      RUNNING MCP SERVER INTEGRATION TEST         ")
    print("==================================================")

    # 1. Start the MCP Server as a subprocess
    server_cmd = [sys.executable, "-m", "mcp_server.server"]
    print(f"Starting MCP server with command: {' '.join(server_cmd)}")
    
    process = subprocess.Popen(
        server_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    time.sleep(1) # Give it a second to start

    try:
        # 2. Send initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        send_request(process, init_req)
        read_response(process)

        # 3. Send notifications/initialized
        notif_req = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        send_request(process, notif_req)
        # Notifications don't get a response

        # 4. List Tools
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        send_request(process, list_req)
        read_response(process)

        # 5. Call Tool: get_all_sources_summary
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_all_sources_summary",
                "arguments": {}
            }
        }
        send_request(process, call_req)
        read_response(process)

        # 6. Call Tool: lookup_safety_threshold
        call_req_2 = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "lookup_safety_threshold",
                "arguments": {
                    "parameter": "fluoride"
                }
            }
        }
        send_request(process, call_req_2)
        read_response(process)

    finally:
        print("\nShutting down MCP server...")
        process.terminate()
        process.wait()
        print("==================================================")
        print("                 TEST COMPLETED                   ")
        print("==================================================")

if __name__ == "__main__":
    main()
