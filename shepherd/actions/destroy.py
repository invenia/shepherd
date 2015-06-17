from shepherd.stack import Stack
from shepherd.common.plugins import Action


class DestroyStack(Action):
    def __init__(self):
        super(DestroyStack, self).__init__()

    def run(self, config, **kwargs):
        assert 'name' in kwargs

        stack = Stack.restore(kwargs['name'], config)
        stack.deprovision_resources()
        stack.save()

        return stack.global_name
