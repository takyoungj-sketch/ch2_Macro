(function () {
  const ROADMAP = [
    {
      group: "데이터 이해",
      items: [
        { n: "01", slug: "data-and-variables", title: "데이터와 변수" },
        { n: "02", slug: "mean-and-median", title: "평균과 중앙값" },
      ],
    },
    {
      group: "기술통계",
      items: [
        { n: "03", slug: "quantiles", title: "분위수" },
        { n: "04", slug: "spread", title: "분산과 표준편차" },
        { n: "05", slug: "iqr-outliers", title: "이상치와 IQR" },
        { n: "06", slug: "sample-size", title: "표본수와 신뢰성" },
      ],
    },
    {
      group: "상관관계",
      items: [{ n: "07", slug: "correlation", title: "상관관계" }],
    },
    {
      group: "회귀분석",
      items: [
        { n: "08", slug: "regression", title: "회귀분석" },
        { n: "09", slug: "log-regression", title: "로그회귀와 변수변환" },
      ],
    },
    {
      group: "모델 평가",
      items: [
        { n: "10", slug: "model-fit", title: "회귀모형의 성능" },
        { n: "11", slug: "cross-validation", title: "교차검증과 CV-MAPE" },
      ],
    },
    {
      group: "통계 결과 읽기",
      items: [{ n: "12", slug: "reading-results", title: "통계 결과를 읽는 법" }],
    },
  ];

  const BASE = "/learn/stats/";

  function slugify(text) {
    return (
      text
        .trim()
        .toLowerCase()
        .replace(/[^\w\u3131-\uD79D\s-]/g, "")
        .replace(/\s+/g, "-")
        .replace(/-+/g, "-")
        .slice(0, 48) || "section"
    );
  }

  function currentSlug() {
    const parts = window.location.pathname.replace(/\/+$/, "").split("/");
    const statsIdx = parts.indexOf("stats");
    if (statsIdx === -1) return null;
    const slug = parts[statsIdx + 1];
    return slug || null;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function buildRoadmapList(container) {
    const title = el("p", "learn-toc__heading", "12장 로드맵");
    container.appendChild(title);
    const nav = el("nav", "learn-toc__chapters");
    nav.setAttribute("aria-label", "학습 로드맵");

    ROADMAP.forEach((group) => {
      const block = el("div", "learn-toc__group");
      block.appendChild(el("p", "learn-toc__group-title", group.group));
      const ul = el("ul", "learn-toc__list");
      group.items.forEach((item) => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = `${BASE}${item.slug}/`;
        a.textContent = `${item.n}. ${item.title}`;
        li.appendChild(a);
        ul.appendChild(li);
      });
      block.appendChild(ul);
      nav.appendChild(block);
    });
    container.appendChild(nav);
  }

  function buildChapterList(container, activeSlug) {
    const title = el("p", "learn-toc__heading", "전체 목차");
    container.appendChild(title);
    const nav = el("nav", "learn-toc__chapters");
    nav.setAttribute("aria-label", "전체 장");

    ROADMAP.forEach((group) => {
      const block = el("div", "learn-toc__group");
      block.appendChild(el("p", "learn-toc__group-title", group.group));
      const ul = el("ul", "learn-toc__list");
      group.items.forEach((item) => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = `${BASE}${item.slug}/`;
        a.textContent = `${item.n}. ${item.title}`;
        if (item.slug === activeSlug) {
          a.classList.add("is-current-chapter");
          a.setAttribute("aria-current", "page");
        }
        li.appendChild(a);
        ul.appendChild(li);
      });
      block.appendChild(ul);
      nav.appendChild(block);
    });
    container.appendChild(nav);
  }

  function ensureSectionIds(article) {
    const used = new Set();
    article.querySelectorAll(".learn-chapter__step").forEach((step, index) => {
      if (step.id) {
        used.add(step.id);
        return;
      }
      const h2 = step.querySelector("h2");
      let id = slugify(h2 ? h2.textContent : `section-${index + 1}`);
      let n = 2;
      while (used.has(id)) {
        id = `${id}-${n++}`;
      }
      step.id = id;
      used.add(id);
    });

    const caution = article.querySelector(".learn-caution");
    if (caution && !caution.id) caution.id = "caution";

    const more = article.querySelector("details.learn-more");
    if (more && !more.id) more.id = "learn-more";

    const cta = article.querySelector(".learn-macro-cta");
    if (cta && !cta.id) cta.id = "macro-cta";
  }

  function buildSectionList(container, article) {
    const title = el("p", "learn-toc__heading learn-toc__heading--sections", "이 장");
    container.appendChild(title);
    const nav = el("nav", "learn-toc__sections");
    nav.setAttribute("aria-label", "이 장 목차");
    const ul = el("ul", "learn-toc__list learn-toc__list--sections");

    article.querySelectorAll(".learn-chapter__step").forEach((step) => {
      const label = step.querySelector(".learn-chapter__label");
      const h2 = step.querySelector("h2");
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `#${step.id}`;
      a.textContent = label ? label.textContent.replace(/\s+/g, " ").trim() : h2?.textContent || "섹션";
      a.dataset.tocTarget = step.id;
      li.appendChild(a);
      ul.appendChild(li);
    });

    const extras = [
      { sel: ".learn-caution", label: "주의" },
      { sel: "details.learn-more", label: "조금 더 알아보기" },
      { sel: ".learn-macro-cta", label: "CH2 Macro" },
    ];
    extras.forEach(({ sel, label }) => {
      const node = article.querySelector(sel);
      if (!node || !node.id) return;
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `#${node.id}`;
      a.textContent = label;
      a.dataset.tocTarget = node.id;
      li.appendChild(a);
      ul.appendChild(li);
    });

    nav.appendChild(ul);
    container.appendChild(nav);
    return nav;
  }

  function setupScrollSpy(sectionNav) {
    const links = sectionNav.querySelectorAll("a[data-toc-target]");
    if (!links.length) return;

    const targets = [...links]
      .map((link) => document.getElementById(link.dataset.tocTarget))
      .filter(Boolean);

    const setActive = (id) => {
      links.forEach((link) => {
        link.classList.toggle("is-active", link.dataset.tocTarget === id);
      });
    };

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -65% 0px", threshold: [0, 0.1, 0.5, 1] },
    );

    targets.forEach((t) => observer.observe(t));

    if (window.location.hash) {
      const id = window.location.hash.slice(1);
      if (document.getElementById(id)) setActive(id);
    }
  }

  function init() {
    const page = document.querySelector(".page");
    if (!page || page.dataset.learnTocInit === "1") return;
    page.dataset.learnTocInit = "1";
    page.classList.add("learn-stats--with-sidebar");

    const slug = currentSlug();
    const article = page.querySelector(".learn-chapter");
    const roadmap = page.querySelector(".learn-roadmap");

    const layout = el("div", "learn-layout");
    const aside = el("aside", "learn-toc");
    aside.setAttribute("aria-label", "목차");
    const inner = el("div", "learn-toc__inner");
    const main = el("div", "learn-main");

    while (page.firstChild) main.appendChild(page.firstChild);

    if (roadmap) {
      aside.classList.add("learn-toc--roadmap");
      buildRoadmapList(inner);
    } else if (article) {
      aside.classList.add("learn-toc--chapter");
      ensureSectionIds(article);
      const sectionNav = buildSectionList(inner, article);
      buildChapterList(inner, slug);
      setupScrollSpy(sectionNav);
    } else {
      aside.classList.add("learn-toc--roadmap");
      buildChapterList(inner, slug);
    }

    const home = document.createElement("a");
    home.href = BASE;
    home.className = "learn-toc__home";
    home.textContent = "← 통계학 & 데이터 분석";
    inner.insertBefore(home, inner.firstChild);

    aside.appendChild(inner);
    layout.appendChild(aside);
    layout.appendChild(main);
    page.appendChild(layout);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
