import fabric
import logging

logging.basicConfig(level=logging.ERROR)
class walker():
    def __init__(self, host_creds):
        self.host_creds = host_creds
        self.connection_register = {}

    def recursive_connector(self, target_host):
        if not self.host_creds.get(target_host):
            raise Exception('Target host not present in the definition data')

        if self.host_creds[target_host].get('via'):
            logging.info('detected a connection with a valid via.')
            gateway_conection = self.recursive_connector(self.host_creds[target_host]['via'])

            logging.info('connecting via: {}'.format(gateway_conection))
            connection_handler = fabric.Connection(self.host_creds[target_host]['hostname'],
                                     user=self.host_creds[target_host]['username'],
                                     connect_kwargs = {'password': self.host_creds[target_host]['password'],
                                                       'allow_agent':False,
                                                       'look_for_keys':False},
                                     gateway=gateway_conection
                                     )
            self.connection_register[target_host] = connection_handler

            return connection_handler
        else:
            connection_handler = fabric.Connection(self.host_creds[target_host]['hostname'],
                                                   user=self.host_creds[target_host]['username'],
                                                   connect_kwargs={'password': self.host_creds[target_host]['password'],
                                                                   'allow_agent': False,
                                                                   'look_for_keys': False}
                                                   )
            self.connection_register[target_host] = connection_handler
            return connection_handler

    def remoteConnect(self, target_host):
        if not self.connection_register.get(target_host):
            return self.recursive_connector(target_host)
        else:
            return self.connection_register.get(target_host)

    def execute(self, host, command):
        connection_handler = None
        if not connection_handler:
            logging.error('Connection handler not defined: {}. reconnecting.'.format(connection_handler))
            connection_handler = self.recursive_connector(host)
        logging.info('working with a connecting handler: {}'. format(connection_handler))
        return connection_handler.run(command, hide=True).stdout
