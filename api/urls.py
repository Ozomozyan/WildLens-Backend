from django.urls import path
from .views import PredictView

urlpatterns = [
    path("predict/", PredictView.as_view(), name="predict"),
]


from rest_framework.routers import SimpleRouter
from .views import PredictionViewSet

router = SimpleRouter(trailing_slash=False)
router.register(r"predictions", PredictionViewSet, basename="predictions")

urlpatterns = router.urls
