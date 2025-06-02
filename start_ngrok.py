from pyngrok import ngrok
import os
import requests
from dotenv import load_dotenv

load_dotenv()

ngrok_authtoken = os.getenv("NGROK_AUTHTOKEN")

def start_ngrok():
    # Kill any existing ngrok processes
    ngrok.kill()
    ngrok.set_auth_token(ngrok_authtoken)
    http_tunnel = ngrok.connect(5000)
    ngrok_url = http_tunnel.public_url
    print(f"Ngrok tunnel established: {ngrok_url}")
    
    # Write the URL to a file
    with open("ngrok_url.txt", "w") as f:
        f.write(ngrok_url)
    
    print("Ngrok URL has been written to ngrok_url.txt")
    
    # Test the URL
    try:
        response = requests.get(f"{ngrok_url}/webhook")
        print(f"Test request status code: {response.status_code}")
    except Exception as e:
        print(f"Error testing URL: {str(e)}")

    ngrok_process = ngrok.get_ngrok_process()
    try:
        ngrok_process.proc.wait()
    except KeyboardInterrupt:
        print(" Shutting down ngrok.")
        ngrok.kill()

if __name__ == "__main__":
    start_ngrok()