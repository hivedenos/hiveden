try:
    from pihole6api import PiHole6Client
except ImportError:
    PiHole6Client = None

class PiHoleManager:
    def __init__(self, host, password):
        if PiHole6Client is None:
            raise ImportError("pihole6api is not installed. Please install it to use Pi-hole features.")
        # Ensure host starts with http/https
        if not host.startswith("http"):
            host = f"http://{host}"
        self.client = PiHole6Client(host, password)

    def list_dns_entries(self):
        """List custom DNS entries."""
        # Use config section for dns/hosts
        if hasattr(self.client, 'config'):
             return self.client.config.get_config_section("dns/hosts")
        return []

    def add_dns_entry(self, domain, ip):
        if hasattr(self.client, 'config'):
            return self.client.config.add_local_a_record(domain, ip)
        raise NotImplementedError("Custom DNS management not supported by current library version.")

    def delete_dns_entry(self, domain, ip):
         if hasattr(self.client, 'config'):
            return self.client.config.remove_local_a_record(domain, ip)
         raise NotImplementedError("Custom DNS management not supported by current library version.")

    def list_blacklist(self):
        if hasattr(self.client, 'domain_management'):
             domains = self.client.domain_management.get_all_domains()
             if domains and 'blacklist' in domains:
                 return domains['blacklist']
        return [] 

    def add_to_blacklist(self, domain):
        # type='deny', match_type='exact'
        return self.client.domain_management.add_domain(domain, "deny", "exact")

    def remove_from_blacklist(self, domain):
        return self.client.domain_management.delete_domain(domain, "deny", "exact")

    def list_whitelist(self):
        if hasattr(self.client, 'domain_management'):
             domains = self.client.domain_management.get_all_domains()
             if domains and 'whitelist' in domains:
                 return domains['whitelist']
        return []

    def add_to_whitelist(self, domain):
        return self.client.domain_management.add_domain(domain, "allow", "exact")

    def remove_from_whitelist(self, domain):
        return self.client.domain_management.delete_domain(domain, "allow", "exact")