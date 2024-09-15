from pyngrok import ngrok
import os
from dotenv import load_dotenv

load_dotenv()

ngrok_authtoken = os.getenv("NGROK_AUTHTOKEN")

def start_ngrok():
    ngrok.set_auth_token(ngrok_authtoken)
    http_tunnel = ngrok.connect(5000)
    ngrok_url = http_tunnel.public_url
    print(f"Ngrok tunnel established: {ngrok_url}")
    
    # Write the URL to a file
    with open("ngrok_url.txt", "w") as f:
        f.write(ngrok_url)
    
    print("Ngrok URL has been written to ngrok_url.txt")
    
    ngrok_process = ngrok.get_ngrok_process()
    try:
        ngrok_process.proc.wait()
    except KeyboardInterrupt:
        print(" Shutting down ngrok.")
        ngrok.kill()

if __name__ == "__main__":
    start_ngrok()