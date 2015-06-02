from shepherd.stack import Stack
from shepherd.common.plugins import Action


class CreateStack(Action):
    def __init__(self):
        super(CreateStack, self).__init__()

    def run(self, config, **kwargs):
        assert 'name' in kwargs

        stack = Stack.make(kwargs['name'], config)
        stack.provision_resources()
        stack.save()
