from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Application
from access_requests.models import RequestItem, OwnerBatch

@receiver(pre_save, sender=Application)
def track_owner_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Application.objects.get(pk=instance.pk)
            instance._old_owner_id = old_instance.owner_id
        except Application.DoesNotExist:
            instance._old_owner_id = None
    else:
        instance._old_owner_id = None

@receiver(post_save, sender=Application)
def update_batch_on_owner_change(sender, instance, created, **kwargs):
    if created:
        return
    
    old_owner_id = getattr(instance, '_old_owner_id', None)
    new_owner_id = instance.owner_id
    
    if old_owner_id != new_owner_id:
        items_to_update = list(RequestItem.objects.filter(
            application=instance,
            status__in=[RequestItem.Status.WAITING_BATCH, RequestItem.Status.PENDING_OWNER]
        ).select_related('batch'))
        
        if not items_to_update:
            return
            
        old_batches = set()
        
        # Get or create new batch
        new_batch = None
        if new_owner_id is not None:
            new_batch = OwnerBatch.objects.filter(
                owner_id=new_owner_id, 
                status=OwnerBatch.Status.WAITING
            ).first()
            if not new_batch:
                new_batch = OwnerBatch.objects.create(owner_id=new_owner_id)
        else:
            new_batch = OwnerBatch.objects.filter(
                owner__isnull=True,
                status=OwnerBatch.Status.WAITING
            ).first()
            if not new_batch:
                new_batch = OwnerBatch.objects.create(owner=None)
                
        # Assign new batch
        for item in items_to_update:
            if item.batch:
                old_batches.add(item.batch)
            item.batch = new_batch
            item.status = RequestItem.Status.WAITING_BATCH
            
        RequestItem.objects.bulk_update(items_to_update, ['batch', 'status'])
        
        # Clean up empty batches
        for old_batch in old_batches:
            if old_batch.items.count() == 0:
                old_batch.delete()
