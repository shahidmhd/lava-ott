from django.core.management import BaseCommand


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('app')
        parser.add_argument('model')
        parser.add_argument('-pk')

    def handle(self, *args, **kwrags):
        app = kwrags.get('app')
        model = kwrags.get('model')
        pk = kwrags.get('pk')
        from django.apps import apps
        model = apps.get_model(app, model)
        if pk:
            try:
                obj = model.objects.get(pk=pk)
            except model.DoesNotExist:
                self.stdout.write(self.style.WARNING('No instance exist.'))
                return
        else:
            obj = model.objects.all()

        obj.delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted successfully!'))
