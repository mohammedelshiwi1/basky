from django.db import models
from core.models import CustomUser
levels = [('easy','easy'),('medium','medium'),('hard','hard')]
class game(models.Model):
    title = models.CharField(max_length=50)
    description = models.TextField()
    level = models.CharField(choices=levels,max_length=10)

    def __str__(self):
        return f'{self.title}'
# Create your models here.
class visit(models.Model):
    type = models.TextField(max_length=30,choices=[('user visit','user visit'),('fast visit','fast visit')])
    name = models.CharField(max_length=50)
    time = models.DateTimeField(auto_now=True)
    score = models.PositiveIntegerField()
    user = models.ForeignKey(CustomUser,on_delete=models.CASCADE)
    required_game = models.ForeignKey(game,on_delete=models.DO_NOTHING)

    def __str__(self):
        return f'{self.name}-{self.time}-{self.score}'

class read(models.Model):
    played_game = models.ForeignKey(game,on_delete=models.DO_NOTHING)
    time = models.DateTimeField(auto_now=True)
    visit = models.ForeignKey(visit,on_delete=models.DO_NOTHING)