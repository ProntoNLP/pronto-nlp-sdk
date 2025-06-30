import mixpanel
import platform


def get_sdk_version():
    """Get SDK version dynamically from setup.py or fallback to default."""
    try:
        # Try to read version from setup.py in the parent directory
        import pkg_resources
        return pkg_resources.get_distribution('pronto-nlp').version
    except:
        # Fallback to hardcoded version
        return '0.5.0'


class APIUserStats:
    
    def __init__(self):
        """
        Initialize Mixpanel tracker.
        """
        self.token = "9e171aa122f0c73dcab137a1dc05b2b8"
        self.api_host = "mixpanel.prontonlp.com"
        self.user_id = None
        self.sdk_version = get_sdk_version()
        self.platform = f"python_{platform.python_version()}_{platform.system().lower()}"
        self.default_properties = {
            'SDK_platform': self.platform,
            'SDK_version': self.sdk_version,
            'source': 'SDK',
        }
        
        try:
            self.mp = mixpanel.Mixpanel(
                self.token, 
                consumer=mixpanel.Consumer(api_host=self.api_host)
            )
        except Exception as e:
            self.mp = None
    
    def identify_user(self, user_obj):
        if not self.mp:
            return
        try:
            self.user_id = user_obj.get('sub')
            properties = {
                '$email': user_obj.get('username'),
                '$name': user_obj.get('https://prontonlp.com/name', ''),
                'SDK_platform': self.platform,
                'SDK_version': self.sdk_version,
                'organization': user_obj.get('https://prontonlp.com/org', '')
            }
            self.mp.people_set(self.user_id, properties)
            self.default_properties = {**self.default_properties, **properties}
        except Exception as e:
            pass
    
    def track(self, event_name, properties=None):
        if not self.mp or not self.user_id:
            return
        merged_properties = {**self.default_properties, **(properties or {})}
        try:
            self.mp.track(self.user_id, event_name, merged_properties)
        except Exception as e:
            pass