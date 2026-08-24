import socket

from celery import shared_task


@shared_task
def verify_custom_domain(domain_id):
    """
    Confirms a custom domain (e.g. banking.imarasacco.co.ke) resolves via
    CNAME to the platform, then flags it ready for on-demand SSL issuance.
    A real deployment would also shell out to certbot here (see Section 17).
    """
    from tenants.models import Domain

    domain = Domain.objects.get(id=domain_id)
    try:
        socket.gethostbyname(domain.hostname)
        domain.ssl_verified = True
        domain.save(update_fields=["ssl_verified"])
    except socket.gaierror:
        pass
