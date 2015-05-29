from abc import ABCMeta

from shepherd.common.plugins import Resource


class AWSResource(Resource):

    __metaclass__ = ABCMeta

    def __init__(self):
        super(AWSResource, self).__init__()
        self._provider = 'aws'
