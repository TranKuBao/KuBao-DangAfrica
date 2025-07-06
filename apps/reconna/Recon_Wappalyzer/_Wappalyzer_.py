#from python_wappalyzer import Wappalyzer, WebPage
from Wappalyzer import Wappalyzer, WebPage
#from Wappalyzer import Wappalyzer,WebPage


class Recon_Wappalyzer:
    def __init__(self, url):
        self.url = url
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