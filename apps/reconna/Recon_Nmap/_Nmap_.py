import os
import sys
import shutil
import nmap
import re
from urllib.parse import urlparse

class Recon_Nmap:
    def __init__(self, target):
        self.target = self.normalize_target(target)
        self._prepare_nmap()
        self.scanner = nmap.PortScanner()

    def _prepare_nmap(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        nmap_dir = os.path.join(current_dir, "Nmap")
        os.environ["PATH"] = nmap_dir + os.pathsep + os.environ["PATH"]

        if not shutil.which("nmap"):
            raise EnvironmentError("❌ Không tìm thấy chương trình 'nmap' trong PATH.")

    def _scan_and_return(self, arguments):
        self.scanner.scan(hosts=self.target, arguments=arguments)
        results = []

        for host in self.scanner.all_hosts():
            host_info = {
                'host': host,
                'state': self.scanner[host].state(),
                'os': [],
                'protocols': {}
            }

            # OS Detection
            if 'osmatch' in self.scanner[host]:
                for osmatch in self.scanner[host]['osmatch']:
                    host_info['os'].append({
                        'name': osmatch['name'],
                        'accuracy': osmatch['accuracy']
                    })

            # Protocols and ports
            for proto in self.scanner[host].all_protocols():
                ports_info = []
                ports = self.scanner[host][proto].keys()
                for port in sorted(ports):
                    data = self.scanner[host][proto][port]
                    ports_info.append({
                        'port': port,
                        'state': data.get('state'),
                        'service': data.get('name'),
                        'product': data.get('product', ''),
                        'version': data.get('version', '')
                    })
                host_info['protocols'][proto] = ports_info

            results.append(host_info)
        return results

    def scan_os(self):
        return self._scan_and_return("-O")

    def scan_services(self):
        return self._scan_and_return("-sV")

    def scan_all(self):
        return self._scan_and_return("-p- -O -sV")

    def scan_custom(self, arguments):
        return self._scan_and_return(arguments)

    @staticmethod
    def normalize_target(target):
        # Nếu là IP thì trả về luôn
        ip_regex = r'^\d{1,3}(?:\.\d{1,3}){3}$'
        if re.match(ip_regex, target):
            return target
        # Nếu là url thì lấy netloc
        if not target.startswith('http'):
            target = 'http://' + target
        try:
            parsed = urlparse(target)
            if parsed.hostname:
                return parsed.hostname
            else:
                return target
        except Exception:
            return target

# scanner = Recon_Nmap("127.0.0.1")
    
# data = scanner.scan_custom("-sVC")  # hoặc .scan_os(), .scan_services(), .scan_custom("-sS -p 80") .scan_all()
# print(data)

# [
#     {'host': '127.0.0.1', 
#      'state': 'up', 
#      'os': [], 
#      'protocols': 
#         {
#             'tcp': 
#                 [
#                 {
#                     'port': 135, 
#                     'state': 'open', 
#                     'service': 'msrpc', 
#                     'product': 'Microsoft Windows RPC', 
#                     'version': ''
#                 }, 
#                 {
#                     'port': 445, 
#                     'state': 'open', 
#                     'service': 'microsoft-ds', 
#                     'product': '', 
#                     'version': ''
#                     }, 
#                 {
#                     'port': 903, 
#                     'state': 'open', 
#                     'service': 'vmware-auth', 
#                     'product': 'VMware Authentication Daemon', 
#                     'version': '1.10'
#                 }, 
#                 {
#                     'port': 7070, 
#                     'state': 'open', 
#                     'service': 'realserver', 
#                     'product': '', 
#                     'version': ''
#                 }
#                 ]
#         }
#     }
# ]