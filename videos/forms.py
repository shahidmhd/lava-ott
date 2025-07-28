from django import forms


class CarouselForm(forms.Form):
    image = forms.ImageField()

    def clean(self):
        images = self.cleaned_data.get('image')
        print(images)
        # if not images:
        #     # self.add_error('image', 'At least one image is required.')
        #     return

        # if images:
        #     if len(images) > 8:
        #         self.add_error('image', 'Maximum 8 carousels are allowed.')
        #
        #     for image in images:
        #         name = image.name.split('.')[-1]
        #         if name not in ('jpg', 'jpeg', 'png'):
        #             self.add_error('image', 'Allowed image formats are jpeg, jpg and png')
