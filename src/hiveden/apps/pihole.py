try:
    from pihole6api import PiHole6Client
except ImportError:
    PiHole6Client = None

class PiHoleManager:
    def __init__(self, host, password, local_domain="hiveden.local"):
        if PiHole6Client is None:
            raise ImportError("pihole6api is not installed. Please install it to use Pi-hole features.")
        # Ensure host starts with http/https
        if not host.startswith("http"):
            host = f"http://{host}"
        self.client = PiHole6Client(host, password)
        self.local_domain = local_domain

    def sync_docker_dns(self):
        """Sync Docker container IPs to Pi-hole DNS."""
        from hiveden.docker.containers import DockerManager
        
        manager = DockerManager()
        containers = manager.list_containers(all=False, only_managed=True) 
        for container in containers:
            if not container.IPAddress:
                continue
            
            ip_address = container.IPAddress
                
            # Process name
            # Use the first name from Names list (usually starts with /)
            raw_name = container.Names[0].lstrip('_')
            
            # Remove 'hiveden' (case-insensitive)
            name = raw_name.lower().replace('hiveden', '')
            
            # Trim '_' and '-' and replace '_' with '-'
            name = name.strip('_-').replace('_', '-')
            
            if not name:
                continue
                
            domain = f"{name}.{self.local_domain}"
            
            try:
                print(f"Adding DNS entry: {domain} -> {ip_address}")
                self.add_dns_entry(domain, ip_address)
            except Exception as e:
                print(f"Failed to add DNS entry for {domain}: {e}")

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