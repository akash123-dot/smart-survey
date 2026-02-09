def user_or_ip(group, request):
    if request.user.is_authenticated:
        return str(request.user.pk)

    return (
        request.META.get("HTTP_X_FORWARDED_FOR")
        or request.META.get("REMOTE_ADDR")
    )
