# base/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    """Main site static pages"""
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            # Main pages
            "landing_page",
            "about",
            "contact",
            "privacy_policy",
            "terms_conditions",
            "register",
            "app_login",
            "blog_index",
            "feed",
            "billing_success",
            "billing_cancel",
            "landing_page_uk",
            "landing_page_dk",
            "app_login_dk",
            "register_dk",
        ]

    def location(self, item):
        return reverse(item)


class BlogSitemap(Sitemap):
    """All blog post pages (static templates)"""
    priority = 0.9
    changefreq = "monthly"

    def items(self):
        return [
            "blog_resume_internship",
            "blog_when_to_apply_for_summer_internships",
            "blog_cover_letter_for_internship",
            "how_to_find_internships_with_no_experience",
            "how_to_get_a_remote_internship",
            "skills_for_internship_resume",
        ]

    def location(self, item):
        return reverse(item)
