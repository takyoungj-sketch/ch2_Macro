(function () {
  const ROADMAP = [
  {
    "group": "I. 데이터와 기술통계",
    "items": [
      {
        "n": "01",
        "slug": "data-and-variables",
        "title": "데이터와 변수",
        "soon": false
      },
      {
        "n": "02",
        "slug": "population-and-sampling",
        "title": "모집단과 표본, 자료 수집과 편향",
        "soon": false
      },
      {
        "n": "03",
        "slug": "graphs",
        "title": "그래프로 보는 데이터와 분포",
        "soon": false
      },
      {
        "n": "04",
        "slug": "mean-and-median",
        "title": "평균과 중앙값",
        "soon": false
      },
      {
        "n": "05",
        "slug": "quantiles",
        "title": "분위수와 상자그림",
        "soon": false
      },
      {
        "n": "06",
        "slug": "spread",
        "title": "분산과 표준편차",
        "soon": false
      },
      {
        "n": "07",
        "slug": "iqr-outliers",
        "title": "이상치와 IQR",
        "soon": false
      }
    ]
  },
  {
    "group": "II. 확률과 표본의 불확실성",
    "items": [
      {
        "n": "08",
        "slug": "probability",
        "title": "확률의 기초와 조건부확률",
        "soon": false
      },
      {
        "n": "09",
        "slug": "probability-distributions",
        "title": "확률변수와 확률분포",
        "soon": false
      },
      {
        "n": "10",
        "slug": "sampling-distributions",
        "title": "표본분포와 중심극한정리",
        "soon": false
      },
      {
        "n": "11",
        "slug": "sample-size",
        "title": "표준오차와 표본수",
        "soon": false
      }
    ]
  },
  {
    "group": "III. 추정과 검정",
    "items": [
      {
        "n": "12",
        "slug": "confidence-intervals",
        "title": "점추정과 신뢰구간",
        "soon": false
      },
      {
        "n": "13",
        "slug": "hypothesis-tests",
        "title": "가설검정과 p값",
        "soon": false
      },
      {
        "n": "14",
        "slug": "comparing-groups",
        "title": "두 집단 비교와 효과크기",
        "soon": false
      },
      {
        "n": "15",
        "slug": "multiple-groups-and-categorical",
        "title": "여러 집단과 범주형 자료의 비교",
        "soon": false
      }
    ]
  },
  {
    "group": "IV. 상관과 회귀",
    "items": [
      {
        "n": "16",
        "slug": "correlation",
        "title": "상관관계와 인과관계",
        "soon": false
      },
      {
        "n": "17",
        "slug": "regression",
        "title": "단순선형회귀와 최소제곱법",
        "soon": false
      },
      {
        "n": "18",
        "slug": "residuals",
        "title": "잔차와 회귀모형의 가정",
        "soon": false
      },
      {
        "n": "19",
        "slug": "multiple-regression",
        "title": "다중회귀와 변수의 해석",
        "soon": false
      },
      {
        "n": "20",
        "slug": "log-regression",
        "title": "로그변환과 비선형 관계",
        "soon": false
      },
      {
        "n": "21",
        "slug": "model-fit",
        "title": "회귀모형의 적합도와 추정의 불확실성",
        "soon": false
      }
    ]
  },
  {
    "group": "V. 예측과 모형 평가",
    "items": [
      {
        "n": "22",
        "slug": "supervised-unsupervised",
        "title": "통계적 설명과 예측, 지도학습과 비지도학습",
        "soon": false
      },
      {
        "n": "23",
        "slug": "train-validation-test",
        "title": "학습·검증·시험 자료와 데이터 누수",
        "soon": true
      },
      {
        "n": "24",
        "slug": "overfitting",
        "title": "과적합과 편향–분산의 균형",
        "soon": false
      },
      {
        "n": "25",
        "slug": "prediction-errors",
        "title": "예측오차: MAE·RMSE·MAPE",
        "soon": true
      },
      {
        "n": "26",
        "slug": "cross-validation",
        "title": "교차검증과 모형 선택",
        "soon": false
      },
      {
        "n": "27",
        "slug": "regularization",
        "title": "규제: 릿지와 라쏘",
        "soon": false
      }
    ]
  },
  {
    "group": "VI. 기초 머신러닝과 종합 해석",
    "items": [
      {
        "n": "28",
        "slug": "classification",
        "title": "분류와 로지스틱 회귀",
        "soon": true
      },
      {
        "n": "29",
        "slug": "knn",
        "title": "최근접 이웃과 변수의 스케일",
        "soon": false
      },
      {
        "n": "30",
        "slug": "decision-tree",
        "title": "의사결정나무",
        "soon": false
      },
      {
        "n": "31",
        "slug": "clustering",
        "title": "군집분석",
        "soon": false
      },
      {
        "n": "32",
        "slug": "reading-results",
        "title": "통계 결과를 읽고 판단하는 법",
        "soon": false
      }
    ]
  }
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

  function itemLabel(item) {
    return item.n ? `${item.n}. ${item.title}` : item.title;
  }

  function appendItem(ul, item, activeSlug) {
    const li = document.createElement("li");
    if (item.soon) {
      const span = el("span", "is-soon", `${itemLabel(item)} · 작성 예정`);
      li.appendChild(span);
      ul.appendChild(li);
      return;
    }
    const a = document.createElement("a");
    a.href = `${BASE}${item.slug}/`;
    a.textContent = itemLabel(item);
    if (activeSlug && item.slug === activeSlug) {
      a.classList.add("is-current-chapter");
      a.setAttribute("aria-current", "page");
    }
    li.appendChild(a);
    ul.appendChild(li);
  }

  function buildRoadmapList(container) {
    const title = el("p", "learn-toc__heading", "과정 목차");
    container.appendChild(title);
    const nav = el("nav", "learn-toc__chapters");
    nav.setAttribute("aria-label", "학습 로드맵");

    ROADMAP.forEach((group) => {
      const block = el("div", "learn-toc__group");
      block.appendChild(el("p", "learn-toc__group-title", group.group));
      const ul = el("ul", "learn-toc__list");
      group.items.forEach((item) => appendItem(ul, item));
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
      group.items.forEach((item) => appendItem(ul, item, activeSlug));
      block.appendChild(ul);
      nav.appendChild(block);
    });
    container.appendChild(nav);
  }

  function ensureSectionIds(article) {
    const used = new Set([...document.querySelectorAll("[id]")].map((node) => node.id));
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
      a.textContent = step.dataset.tocLabel || h2?.textContent || label?.textContent || "섹션";
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
      if (!node || !node.id || node.closest(".learn-chapter__step")) return;
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

    let pending = false;
    function update() {
      pending = false;
      const marker = Math.min(180, window.innerHeight * 0.25);
      let current = targets[0];
      let nearest = -Infinity;
      for (const target of targets) {
        const top = target.getBoundingClientRect().top;
        if (top <= marker && top > nearest) { current = target; nearest = top; }
      }
      if (current) setActive(current.id);
    }
    window.addEventListener("scroll", () => {
      if (!pending) { pending = true; requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  function init() {
    const page = document.querySelector(".page");
    if (!page || page.dataset.learnTocInit === "1") return;
    page.dataset.learnTocInit = "1";
    page.classList.add("learn-stats--with-sidebar");

    const slug = currentSlug();
    const article = page.querySelector(".learn-chapter");
    const roadmap = page.querySelector(".learn-roadmap");
    const header = page.querySelector(":scope > header.hero");

    const layout = el("div", "learn-layout");
    const aside = el("aside", "learn-toc");
    aside.setAttribute("aria-label", "목차");
    const inner = el("div", "learn-toc__inner");
    const main = el("div", "learn-main");

    [...page.childNodes].forEach((node) => {
      if (node !== header) main.appendChild(node);
    });

    if (roadmap) {
      aside.classList.add("learn-toc--roadmap");
      buildRoadmapList(inner);
    } else if (article) {
      aside.classList.add("learn-toc--chapter");
      ensureSectionIds(article);
      const sectionNav = buildSectionList(inner, article);
      const course = el("details", "learn-course-details");
      course.appendChild(el("summary", "", "전체 과정 목차"));
      buildChapterList(course, slug);
      inner.appendChild(course);
      requestAnimationFrame(() => setupScrollSpy(sectionNav));
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
    layout.appendChild(main);
    layout.appendChild(aside);
    page.appendChild(layout);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
