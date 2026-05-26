// Extracted from courses/landing.html
    (function () {
        var header = document.querySelector(".landing-header");
        var toggle = document.getElementById("landing-nav-toggle");
        var menu = document.getElementById("landing-menu");
        if (!header || !toggle || !menu) return;

        function setOpen(open) {
            header.classList.toggle("landing-header--nav-open", open);
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
            toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
        }

        toggle.addEventListener("click", function () {
            setOpen(!header.classList.contains("landing-header--nav-open"));
        });

        menu.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                if (window.matchMedia("(max-width: 768px)").matches) {
                    setOpen(false);
                }
            });
        });

        window.addEventListener("resize", function () {
            if (!window.matchMedia("(max-width: 768px)").matches) {
                setOpen(false);
            }
        });
    })();

    // Scroll-triggered section / card reveals (IntersectionObserver)
    (function () {
        var staggerSelectors = [
            ".features-grid .feature-card.reveal-item",
            ".testimonials-grid .testimonial-card.reveal-item",
            ".pricing-grid .pricing-card.reveal-item",
            "#blog-posts-grid .blog-card.reveal-item",
        ];
        var observed = new WeakSet();
        var observer = null;

        function prefersReducedMotion() {
            return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        }

        function applyStaggerDelays() {
            staggerSelectors.forEach(function (sel) {
                document.querySelectorAll(sel).forEach(function (el, i) {
                    el.style.setProperty("--reveal-delay", Math.min(i * 65, 520) + "ms");
                });
            });
        }

        function revealAll() {
            document.querySelectorAll(".reveal-section, .reveal-item").forEach(function (el) {
                el.classList.add("is-revealed");
            });
        }

        function startObserver() {
            if (prefersReducedMotion()) {
                revealAll();
                return;
            }
            if (!observer) {
                observer = new IntersectionObserver(
                    function (entries) {
                        entries.forEach(function (entry) {
                            /* Toggle so the transition replays every time you scroll past */
                            if (entry.isIntersecting) {
                                entry.target.classList.add("is-revealed");
                            } else {
                                entry.target.classList.remove("is-revealed");
                            }
                        });
                    },
                    { root: null, rootMargin: "0px 0px -6% 0px", threshold: 0.1 }
                );
            }
            document.querySelectorAll(".reveal-section, .reveal-item").forEach(function (el) {
                if (observed.has(el)) return;
                observed.add(el);
                observer.observe(el);
            });
        }

        function initLandingScrollReveal() {
            applyStaggerDelays();
            startObserver();
        }

        window.initLandingScrollReveal = initLandingScrollReveal;

        function boot() {
            initLandingScrollReveal();
        }

        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", boot);
        } else {
            boot();
        }
    })();

    // Smooth scroll for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            }
        });
    });


    // Fallback blog posts for offline display
    const FALLBACK_POSTS = [
        {
            id: 1,
            title: 'From Layered to Space-Based: A Practical Guide to Software Architecture Styles',
            excerpt: 'Understanding the differences between architectural patterns and choosing the right one for your project can make or break scalability. In this post, we explore layer-based, space-based, and event-driven architectures with practical examples.',
            date: '5/3/2026',
            tag: 'Architecture',
            author: 'Admin',
            image: '/media/images/landing_page/blog-architecture.png'
        },
        {
            id: 2,
            title: 'How to Think About API Design Before You Write a Single Route',
            excerpt: 'Good API design isn\'t about choosing the "coolest" tech stack. It\'s about clarity, consistency, and thinking from your consumer\'s perspective. We break down the principles of REST, GraphQL, and RPC-style APIs.',
            date: '4/18/2026',
            tag: 'Backend',
            author: 'Admin',
            image: '/media/images/landing_page/blog-api-design.png'
        },
        {
            id: 3,
            title: 'Front-End Performance That Actually Ships',
            excerpt: 'Performance metrics are only useful if they translate to real user experience improvements. Learn about Core Web Vitals, bundle optimization, and the tools that matter in production environments.',
            date: '4/7/2026',
            tag: 'Front-end',
            author: 'Admin',
            image: '/media/images/landing_page/blog-performance.png'
        },
        {
            id: 4,
            title: 'Writing Code Reviews That Build, Not Break, Your Team',
            excerpt: 'Code reviews are about more than catching bugs—they\'re about building trust and sharing knowledge. Discover how to write feedback that improves code without bruising egos.',
            date: '3/22/2026',
            tag: 'Engineering culture',
            author: 'Admin',
            image: '/media/images/landing_page/blog-code-reviews.png'
        }
    ];

    // Blog post fetching and rendering IIFE
    (function initializeBlog() {
        const blogGrid = document.getElementById('blog-posts-grid');
        if (!blogGrid) return;

        async function fetchBlogPosts() {
            try {
                // Try primary API endpoint
                const response = await fetch('https://mblog-frl0.onrender.com/api/posts/', {
                    headers: { 'Accept': 'application/json' }
                });

                if (!response.ok) throw new Error('API response not ok');
                const data = await response.json();

                // Ensure we have a usable array
                if (!Array.isArray(data) && data.results && Array.isArray(data.results)) {
                    return data.results.slice(0, 4); // Take first 4 posts
                }
                if (!Array.isArray(data)) throw new Error('Invalid data format');

                return data.slice(0, 4);
            } catch (error) {
                console.warn('Could not fetch blog posts:', error);
                return FALLBACK_POSTS;
            }
        }

        function buildBlogCard(post) {
            const url = post.url || `https://mblog-frl0.onrender.com/posts/${post.slug || post.id}`;
            const title = post.title || 'Untitled Post';
            const excerpt = (post.content || post.excerpt || '').substring(0, 140) + '...';
            const date = post.date ? new Date(post.date).toLocaleDateString('en-US', { year: 'numeric', month: 'numeric', day: 'numeric' }) : post.date || 'Recently';
            const tag = post.category || post.tag || 'Article';
            const image = post.image || post.featured_image || '/media/images/landing_page/blog-architecture.png';

            return `
                <a href="${url}" target="_blank" rel="noopener noreferrer" class="blog-card reveal-item reveal-on-scroll">
                    <div class="blog-card__img">
                        <img src="${image}" alt="${title}" loading="lazy" onerror="this.src='/media/images/landing_page/blog-architecture.png'">
                    </div>
                    <div class="blog-card__body">
                        <div class="blog-card__meta">
                            <span class="blog-card__tag">${escapeHtml(tag)}</span>
                            <span class="blog-card__date">${escapeHtml(date)}</span>
                        </div>
                        <h3 class="blog-card__title">${escapeHtml(title)}</h3>
                        <p class="blog-card__excerpt">${escapeHtml(excerpt)}</p>
                        <span class="blog-card__read-more">
                            Read article
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M3 8h10M8 3l5 5-5 5"></path>
                            </svg>
                        </span>
                    </div>
                </a>
            `;
        }

        function escapeHtml(text) {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, char => map[char]);
        }

        async function renderBlogPosts() {
            const posts = await fetchBlogPosts();

            // Clear skeleton loaders
            blogGrid.innerHTML = '';

            // Render blog cards
            const cardsHtml = posts.map(post => buildBlogCard(post)).join('');
            blogGrid.innerHTML = cardsHtml;

            if (typeof window.initLandingScrollReveal === 'function') {
                window.initLandingScrollReveal();
            }
        }

        // Render posts when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', renderBlogPosts);
        } else {
            renderBlogPosts();
        }
    })();
