from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from blog.form import PostForm, CommentForm, UserProfileForm
from blog.models import Category, Comment, Post, User


def get_posts(
    posts=Post.objects,
    filter_published=False,
    fetch_related=False,
    count_comments=False,
):
    if filter_published:
        posts = posts.filter(
            pub_date__lte=timezone.now(),
            is_published=True,
            category__is_published=True
        )

    if fetch_related:
        posts = posts.select_related('category', 'location', 'author')

    if count_comments:
        posts = posts.annotate(comment_count=Count('comments'))

    ordering = posts.model._meta.ordering
    if ordering:
        posts = posts.order_by(*ordering)

    return posts


def paginate_posts(request, posts, per_page=10):
    return Paginator(posts, per_page).get_page(request.GET.get('page'))


class CommentBaseMixin:
    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'
    context_object_name = 'comment'

    def get_queryset(self):
        return get_object_or_404(
            Post,
            pk=self.kwargs['post_id']
        ).comments.select_related('author')

    def test_func(self):
        return self.get_object().author == self.request.user

    def handle_no_permission(self):
        return redirect('blog:post_detail', post_id=self.kwargs['post_id'])

    def get_success_url(self):
        return reverse('blog:post_detail', args=[self.kwargs['post_id']])


class CommentCreateView(LoginRequiredMixin, CreateView):
    model = Comment
    form_class = CommentForm

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = get_object_or_404(Post, pk=self.kwargs['post_id'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:post_detail', args=[self.kwargs['post_id']])


class CommentUpdateView(
    LoginRequiredMixin, CommentBaseMixin, UserPassesTestMixin, UpdateView
):
    form_class = CommentForm


class CommentDeleteView(
    LoginRequiredMixin, CommentBaseMixin, UserPassesTestMixin, DeleteView
):
    pass


class OnlyAuthorMixin(UserPassesTestMixin):

    def test_func(self):
        return self.get_object().author == self.request.user

    def handle_no_permission(self):
        return redirect('blog:post_detail', post_id=self.kwargs['post_id'])


class ProfileDetailView(DetailView):
    model = User
    slug_field = 'username'
    slug_url_kwarg = 'username'
    template_name = 'blog/profile.html'
    context_object_name = 'profile'

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            **kwargs,
            page_obj=paginate_posts(
                self.request,
                get_posts(
                    self.object.posts,
                    filter_published=self.request.user != self.object,
                    fetch_related=True,
                    count_comments=True
                )
            )
        )


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile', args=[self.request.user.username])


class PostUpdateView(OnlyAuthorMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def get_success_url(self):
        return reverse('blog:post_detail', args=[self.kwargs['post_id']])


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user}
        )


class PostDeleteView(LoginRequiredMixin, OnlyAuthorMixin, DeleteView):
    model = Post
    success_url = reverse_lazy('blog:index')
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            **kwargs,
            form=PostForm(isinstance=self.object)
        )


def index(request):
    return render(
        request,
        'blog/index.html',
        {
            'page_obj': paginate_posts(
                request,
                get_posts(
                    filter_published=True,
                    fetch_related=True,
                    count_comments=True
                )
            )
        }
    )


def post_detail(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        post = get_object_or_404(
            get_posts(filter_published=True),
            pk=post_id
        )
    return render(
        request, 'blog/detail.html',
        {
            'post': post,
            'comments': post.comments.select_related('author').all(),
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
                request,
                get_posts(
                    category.posts,
                    filter_published=True,
                    fetch_related=True,
                    count_comments=True
                )
            )
        }
    )
