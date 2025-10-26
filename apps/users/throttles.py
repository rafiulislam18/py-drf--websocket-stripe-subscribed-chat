from rest_framework.throttling import AnonRateThrottle


class RegisterThrottle(AnonRateThrottle):
    # Custom limit for registration
    rate = "5/minute"

class HighLimitAnonRateThrottle(AnonRateThrottle):
    # Custom throttle with high limit (for login, logout, token refresh)
    rate = "180/minute"
