import logging

from socorro.middleware.service import DataAPIService

logger = logging.getLogger("webapi")


class VersionsInfo(DataAPIService):

    """
    Return information about versions of a product.
    """

    service_name = "util"
    uri = "/util/versions_info/(.*)"

    def __init__(self, config):
        """
        Constructor
        """
        super(VersionsInfo, self).__init__(config)
        logger.debug('Search service __init__')

    def get(self, *args):
        """
        Called when a get HTTP request is executed to /search
        """
        params = self.parse_query_string(args[0])

        module = self.get_module(params)
        impl = module.Util(config=self.context)

        return impl.versions_info(**params)
