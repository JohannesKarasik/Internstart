from django.shortcuts import render

# Create your views here.
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404, render
from .models import BlogPost

def blog_index(request):
    qs = BlogPost.objects.filter(status="published").order_by("-published_at", "-created_at")
    paginator = Paginator(qs, 9)  # 9 per page
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "page_obj": page_obj,
        "posts": page_obj.object_list,  # convenience
        "paginator": paginator,
    }
    return render(request, "blog/index.html", context)


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, status="published")
    return render(request, "blog/detail.html", {"post": post})
