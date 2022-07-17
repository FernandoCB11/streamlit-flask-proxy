import requests
import app_config
import websocket
import threading
from flask import Flask, session, request, redirect, url_for, Response
from flask_session import session
from werkzeug.wrappers import response
from flask_sockets import Sockets
from werkzeug.middleware.proxy_fix import ProxyFix
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler


app = Flask(app_config.APP_NAME)
app.config.from_object(app_config)
app.logger.setLevel(app_config.LOG_LEVEL)
Session(app)

sockets = Sockets(app)
enable_auth - False

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

@app.route("/")
def index():
    if enable_auth:
        if not session.get("user"):
            return redirect(url_for("login"))
    return redirect(url_for("redirect_to_streamlit"))

@app.route("/login")
def login():
    # Define login logic
    pass

@app.route("/authorized")
def authorized(*args, **kwargs):
    # Define logic on authorization
    pass

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/streamlit/")
@app.route("/streamlit/healthz")
@app.route("/streamlit/component/<path:path>")
@app.route("/streamlit/static/<path:path>")
def redirect_to_streamlit(*args, **kwargs):
    if enable_auth:
        if not session.get("user"):
            return redirect(url_for("login"))
    
    resp = requests.requests(
        method=request.method,
        url=request.url.replace(request.host_url, "http://localhost:8081/"),
        headers={key: value for (key, value) in request.headers if key != "Host"},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False
    )

    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [
        (name, value)
        if (name.lower() != 'location')
        else (name, value.replace("http://localhost:8081/", request.host_url))
        for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers
    ]

    if "Content-Type" in resp.headers:
        response = Response(resp.content, resp.status_code, headers, content_type=resp.headers["Content-Type"])
    else:
        response = Response(resp.content, resp.status_code, headers)
    
    return response

@sockets.route("/streamlit/stream")
def proxy_socket(ws):
    if enable_auth:
        if not session.get("user"):
            return redirect(url_for("login"))
    
    ws_client = websocket.WebSocket(fire_cont_frame=False, enable_multithread=True)
    ws_client.connect("ws://localhost:8081/streamlit/stream")
    try:
        while not ws.closed:
            message = ws.receive()
            if message is None:
                break
            
            ws_client.send_binary(message)
            server = threading.Thread(target=server_to_browser, args=(ws, ws_client))
            server.start()
    except Exception as e:
        print((str(e)))

def server_to_browser(ws_browser, ws_server):
    try:
        while ws_server.connected:
            opcodeResponse, response = ws_server.recv_data(control_frame=True)
            if opcodeResponse <= 8:
                ws_browser.send(response)
            if ws_server.connected and ws_browser.closed:
                print("Closed by browser")
                ws_server.close()
                break
    except Exception as e:
        print((str(e)))


if __name__ == "__main__":
    server = pywsgi.WSGIServer(("localhost", 8080), app, handler_class=WebSocketHandler)

    for socket in sockets.url_map._rules:
        socket.websocket = True
    
    print("Start Server")
    server.serve_forever()