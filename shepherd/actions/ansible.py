from shepherd.stack import Stack
from shepherd.common.plugins import Action


class AnsibleConfigure(Action):
    def __init__(self):
        super(AnsibleConfigure, self).__init__()

    def run(self, config, **kwargs):
        assert 'name' in kwargs
        assert 'playbook' in kwargs

        stack = Stack.restore(kwargs['name'], config)
        # generate inventory file from stack instance ips

        # check if playbook is path or URL. If URL clone to tmp.

        # cmd = ['ansible-playbook', '-i', inventory, os.path.basename(playbook)]
        # add vault-password-file or vault-pass if supplied in kwargs
        # add other params like tags if provided.
        return stack
