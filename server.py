from datetime import datetime, timedelta
import urllib3

try:
    import socketserver as SocketServer
    import http.server as SimpleHTTPServer
except ImportError:
    import SocketServer
    import SimpleHTTPServer

cache = {}

# Class xu ly request den proxy server
class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    remote_response = None
    blacklist_urls = []

    def __init__(self, *args, **kwargs):
        self.load_blacklist_file()
        super(RequestHandler, self).__init__(*args, **kwargs)

    def load_blacklist_file(self):
        """
        Load file blacklist
        :return:
        """
        try:
            f = open('blacklist.conf', 'r')
            self.blacklist_urls = list([line for line in f])
            f.close()
        except FileNotFoundError:
            pass

    def do_GET(self):
        """
        Xu ly GET request
        :return:
        """
        self.handle_get_request()

    def do_POST(self):
        """
        Xu ly POST request
        :return:
        """
        data = self.read_request_data()
        self.handle_post_request(data)

    def read_request_data(self):
        """
        Doc data tu client den proxy server
        :return:
        """
        header_value = self.headers['Content-Length']
        data_length = int(header_value) if header_value is not None else None
        return self.rfile.read(data_length) if data_length is not None else None

    def remote_request_header(self):
        """
        Regular cac header duoc gui den remote server
        :return:
        """
        _h = dict(self.headers)
        _h['Accept-Encoding'] = 'identity'  # Khong encode data vi co mot so van de client se khong doc duoc data encoded
        return _h

    def handle_post_request(self, data):
        """
        Xu ly POST request
        :param data:
        :return:
        """
        if self.is_blacklisted():
            self.respond_forbidden()
            return
        self.resp = self.connection_pool.request('POST', self.path, headers=self.remote_request_header(), body=data)
        self.respond()

    def handle_get_request(self):
        """
        Xu ly GET request
        :return:
        """
        if self.is_blacklisted():
            self.respond_forbidden()
            return
        # Load cache
        cache_hit = False
        if cache.get(self.path) and \
                cache.get(self.path)['time'] + timedelta(minutes=5) > datetime.now() :
            self.resp = cache[self.path]['data']
            cache_hit = True
        else:
            self.resp = self.connection_pool.request('GET', self.path, headers=self.remote_request_header())
            cache[self.path] = {
                'data': self.resp,
                'time': datetime.now(),
            }
        self.respond(cache_hit)

    @property
    def connection_pool(self):
        """
        Connection object dung de make request den remote server
        :return:
        """
        if not hasattr(self, 'c_pool'):
            self.c_pool = urllib3.PoolManager(maxsize=50)
        return self.c_pool

    def is_blacklisted(self):
        """
        Kiem tra remote website co nam trong black list hay khong
        :return:
        """
        domain = self.path.replace('http://', '').split('/')[0]
        return domain in self.blacklist_urls

    def respond_forbidden(self):
        """
        Response 403 cho nhung trang bi blacklisted
        :return:
        """
        self.send_error(403 , 'Forbidden')
        self.wfile.write(b'Forbidden')

    def respond(self, cache_hit=False):
        self.send_response_only(self.resp.status)   # Gui Status code dau tien + version htttp
        for key, value in self.resp.headers.items():    # gui cac header tu remote server
            self.send_header(key, value)
        if cache_hit:
            self.send_header('X-Proxy-Cache', 'hit')    # The hien co cache
        self.end_headers()
        self.wfile.write(self.resp.data)                # Gui data cua remote server den client


# Class extend de ho tro chay server multi-thread
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

# Wrapper class de start server
class ProxyBox(object):

    def __init__(self):
        self.port = 8888
        self.base_url = '0.0.0.0'

        self.server = ThreadedTCPServer((self.base_url, self.port), RequestHandler)

    def start(self):
        print('PROXY SERVER LISTENING ON http://' + self.base_url + ':' + str(self.port))
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()
        self.server.server_close()

if __name__ == '__main__':
    box = ProxyBox()
    try:
        box.start()
    except KeyboardInterrupt:
        box.shutdown()
        print('Shutdown.')

