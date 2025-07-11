#from python_wappalyzer import Wappalyzer, WebPage
from Wappalyzer import Wappalyzer, WebPage
#from Wappalyzer import Wappalyzer,WebPage
from multiprocessing import Process, Queue
import re
from urllib.parse import urlparse


class Recon_Wappalyzer:
    _process = None
    _queue = None
    _result = None

    @staticmethod
    def _scan_worker(url, queue):
        try:
            scanner = Recon_Wappalyzer(url)
            result = scanner.get_results()
            queue.put(result)
        except Exception as e:
            queue.put({'error': str(e)})



    @staticmethod
    def start_scan(url):
        if Recon_Wappalyzer._process is not None and Recon_Wappalyzer._process.is_alive():
            return False, 'A scan is already running'
        Recon_Wappalyzer._queue = Queue()
        Recon_Wappalyzer._process = Process(target=Recon_Wappalyzer._scan_worker, args=(url, Recon_Wappalyzer._queue))
        Recon_Wappalyzer._process.start()
        Recon_Wappalyzer._result = None
        return True, 'Wappalyzer is scanning...'

    @staticmethod
    def get_scan_result():
        if Recon_Wappalyzer._result is not None:
            return Recon_Wappalyzer._result
        if Recon_Wappalyzer._queue is not None and not Recon_Wappalyzer._queue.empty():
            Recon_Wappalyzer._result = Recon_Wappalyzer._queue.get()
            return Recon_Wappalyzer._result
        return None

    @staticmethod
    def stop_scan():
        if Recon_Wappalyzer._process is not None and Recon_Wappalyzer._process.is_alive():
            Recon_Wappalyzer._process.terminate()
            Recon_Wappalyzer._process = None
            return True, 'Scan stopped'
        else:
            return False, 'No scan is running'

    @staticmethod
    def normalize_target(target):
        # Nếu là IP thì thêm http://
        ip_regex = r'^\\d{1,3}(?:\\.\\d{1,3}){3}$'
        if re.match(ip_regex, target):
            return 'http://' + target
        # Nếu là url thiếu scheme thì thêm http://
        if not target.startswith('http://') and not target.startswith('https://'):
            target = 'http://' + target
        return target

    def __init__(self, url):
        self.url = self.normalize_target(url)
        self.webpage = WebPage.new_from_url(self.url)
        self.wappalyzer = Wappalyzer.latest()
        self.technologies = self.wappalyzer.analyze_with_versions(self.webpage)
        self.tech_list = self._extract_tech_list()

    def _extract_tech_list(self):
        tech_list = []
        for tech, data in self.technologies.items():
            version = ', '.join(data['versions']) if 'versions' in data and data['versions'] else 'Unknown'
            tech_list.append({
                'technology': tech,
                'version': version
            })
        return tech_list

    def print_results(self):
        for item in self.tech_list:
            print(f"{item['technology']} - Ver: {item['version']}")

    def get_results(self):
        return self.tech_list

#print(Recon_Wappalyzer('http://testphp.vulnweb.com/')._extract_tech_list())