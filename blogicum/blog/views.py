from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.query import QuerySet
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from blog.form import PostForm, CommentForm
from blog.models import Category, Comment, Post

User = get_user_model()


def count_comments(posts: QuerySet | None = None):
    if posts is None:
        posts = Post.objects.all()

    return posts.annotate(comment_count=Count('comment')).order_by('-pub_date')


def get_post_for_detail(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related('category', 'location', 'author'),
        pk=post_id
    )
    category_is_published = (
        post.category is not None and post.category.is_published
    )

    if (
        post.is_published
        and category_is_published
        and post.pub_date <= timezone.now()
    ):
        return post
    if request.user.is_authenticated and request.user == post.author:
        return post

    raise Http404


def paginate_posts(request, posts):
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return page_obj


def get_published_posts(posts: QuerySet | None = None):
    if posts is None:
        posts = Post.objects.all()

    posts = posts.select_related(
        'category', 'location', 'author'
    ).filter(
        pub_date__lte=timezone.now(),
        is_published=True,
        category__is_published=True
    )

    return count_comments(posts)


class CommentCreateView(LoginRequiredMixin, CreateView):
    current_post = None
    model = Comment
    form_class = CommentForm

    def dispatch(self, request, *args, **kwargs):
        self.current_post = get_post_for_detail(request, kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = self.current_post
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.current_post.pk}
        )


class CommentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'
    context_object_name = 'comment'

    def get_queryset(self):
        return Comment.objects.select_related('post', 'author').filter(
            post_id=self.kwargs['post_id']
        )

    def test_func(self):
        comment = self.get_object()
        return comment.author == self.request.user

    def handle_no_permission(self):
        comment = self.get_object()
        return redirect('blog:post_detail', post_id=comment.post.pk)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.object.post.pk}
        )


class CommentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'
    context_object_name = 'comment'

    def get_queryset(self):
        return Comment.objects.select_related('post', 'author').filter(
            post_id=self.kwargs['post_id']
        )

    def test_func(self):
        comment = self.get_object()
        return comment.author == self.request.user

    def handle_no_permission(self):
        comment = self.get_object()
        return redirect('blog:post_detail', post_id=comment.post.pk)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.object.post.pk}
        )


class OnlyAuthorMixin(UserPassesTestMixin):

    def test_func(self):
        obj = self.get_object()
        return obj.author == self.request.user

    def handle_no_permission(self):
        return redirect('blog:post_detail', post_id=self.get_object().pk)


class ProfileDetailView(DetailView):
    model = User
    slug_field = 'username'
    slug_url_kwarg = 'username'
    template_name = 'blog/profile.html'
    context_object_name = 'profile'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user == self.object:
            posts = count_comments(self.object.posts.all())
        else:
            posts = get_published_posts(self.object.posts.all())
        context['page_obj'] = paginate_posts(self.request, posts)
        return context


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class PostUpdateView(OnlyAuthorMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.object.pk}
        )


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    fields = ('first_name', 'last_name', 'username', 'email')
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.object.username}
        )


class PostDeleteView(LoginRequiredMixin, OnlyAuthorMixin, DeleteView):
    model = Post
    success_url = reverse_lazy('blog:index')
    template_name = 'blog/create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm(instance=self.object)
        return context


def index(request):
    return render(
        request,
        'blog/index.html',
        {'page_obj': paginate_posts(request, get_published_posts())}
    )


def post_detail(request, post_id):
    post = get_post_for_detail(request, post_id)
    return render(
        request, 'blog/detail.html',
        {
            'post': post,
            'comments': post.comment.select_related('author').all(),
            'form': CommentForm(),
        }
    )


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category,
        slug=category_slug,
        is_published=True
    )
    return render(
        request,
        'blog/category.html',
        {
            'category': category,
            'page_obj': paginate_posts(
                request, get_published_posts(category.posts.all())
            )
        }
    )
