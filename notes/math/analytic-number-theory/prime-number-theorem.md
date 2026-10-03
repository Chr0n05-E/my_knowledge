---
id: math/analytic-number-theory/prime-number-theorem
title: 素数定理
type: concept
parents: [math/analytic-number-theory]
aliases: [Prime Number Theorem, PNT]
tags: [数论, 素数, zeta函数]
status: growing
created: 2026-02-14
updated: 2026-02-14
---

# 素数定理

## 定义

记 $\pi(x)$ 为不超过 $x$ 的素数个数，则

$$\pi(x) \sim \frac{x}{\ln x} \quad (x \to \infty), \qquad \text{等价地} \quad p_n \sim n \ln n,$$

其中 $p_n$ 是第 $n$ 个素数。更好的逼近是积分对数 $\operatorname{li}(x) = \int_2^x \frac{dt}{\ln t}$，因为 $\operatorname{li}(x) = \frac{x}{\ln x} + \frac{x}{\ln^2 x} + \cdots$，它把误差项压得更小。

## 我的理解

素数看上去是"局部随机"的（相邻间隔忽大忽小），但把它们**累计起来看**，密度却光滑地衰减，局部密度约为 $1/\ln x$。这本身就是耐人寻味的事实：随机性在求和之后消失了。

为什么是 $1/\ln x$？我记住的推导直觉是"筛法式的概率模型"：$n$ 不被 2 整除的概率是 $1/2$，不被 3 整除是 $2/3$……若近似独立，则

$$\prod_{p \le x}\left(1 - \frac{1}{p}\right) \approx \frac{e^{-\gamma}}{\ln x},$$

于是 $x$ 以内"没被任何小素数筛掉"的数的个数约为 $e^{-\gamma} x / \ln x$。这个乘积的衰减正是 $\ln x$ 的来源。Mertens 定理给了它严格形式。这个启发式解释了**为什么有 $\ln$**，但它不构成证明——独立性假设本身就是需要论证的东西。

真正的证明路径是：定义 Chebyshev 函数 $\psi(x) = \sum_{p^k \le x} \ln p$，用 Abel 求和把它与 $\zeta$ 的对数导数连起来：

$$-\frac{\zeta'(s)}{\zeta(s)} = \sum_{n\ge1} \frac{\Lambda(n)}{n^s},$$

再做 Perron 公式的反演（一个复积分），证明 $\psi(x) \sim x$，并由此推出 $\pi(x) \sim x/\ln x$。整条链条的**唯一实质障碍**是 $\zeta(s)$ 在 $\operatorname{Re} s = 1$ 上不为零——这也是我从这个定理里得到的最重要的理解：**素数的分布问题被完整地翻译成了复变函数的零点位置问题**。

## 直觉 / 为什么

- $\zeta(s) = \prod_p (1 - p^{-s})^{-1}$ 的欧拉乘积把"整数的乘法结构"装进了一个复变函数。$\zeta$ 的极点与零点是整数世界的"奇点"。
- 在 $s = 1$ 处的单极点强度（留数 1）对应"素数无穷多且密度恰好是 $1/\ln x$"。黎曼假设（零点都在 $\operatorname{Re} s = 1/2$）等价于把误差项压到 $O(\sqrt{x}\ln x)$——也就是"素数分布最规则的样子"。
- 所以 PNT 与 RH 不是两件事，而是同一件事的两个精度档位。

## 关键结论

- $\pi(x) \sim x/\ln x \iff \psi(x) \sim x$（等价形式，用 Abel/分部求和互相推出）。
- 初等证明存在（Selberg–Erdős，1949），但换不来误差项，也换不来 RH 那类精细信息。
- 误差界：无条件已知 $\pi(x) = \operatorname{li}(x) + O\!\left(x \exp(-c\sqrt{\ln x})\right)$（Vinogradov–Korobov 型）。
- 小素数区间上 $\operatorname{li}(x) > \pi(x)$ 长期成立，但 Skewes 数表明差值符号会翻转——**小样本验证不出渐近真理**，这是我最喜欢的一个反直觉例子。

## 边界与反例

- "素数的密度是 $1/\ln x$"是渐近陈述，**不表示**在任意区间都成立：$[n, n + c\ln^2 n]$ 内必有素数（RH 下成立），而无条件的结果是 $[n, n+n^{0.525}]$。局部行为可以很怪（大素数间隙）。
- 常见误解：以为 PNT 能给出"第 $n$ 个素数是多少"的精确公式。它只给渐近，且误差主项之外还有振荡项（显式公式里由零点贡献）。
- PNT 完全不涉及哥德巴赫、孪生素数这类"加性/结构性"问题——它只谈计数。

## 与其它概念的关系

- 属于：[[math/analytic-number-theory|解析数论]]
- 依赖：$\zeta$ 函数与欧拉乘积、复分析（留数定理、Perron 公式）、Abel 求和
- 对比：[[engineering/computer-science/algorithms/binary-search|二分查找]] 里的"信息论下界"式论证——一个给出不可逾越的界，一个构造达到它的方法，思路同源但方向相反

## 未解决的问题

- 我想自己完整推一遍"$\zeta(1+it) \ne 0$ 推出 PNT"这一段，现在只会背结论。
- 显式公式 $\psi(x) = x - \sum_\rho \frac{x^\rho}{\rho} - \cdots$ 里每一项到底对应什么直觉图像，我还没有真的搞懂。

## 参考

- 潘承洞、潘承彪《素数定理的初等证明》（想跟着走一遍 Selberg 路线）
- Apostol, *Introduction to Analytic Number Theory*，第 3–4 章（Chebyshev 函数与等价形式）
- Newman 的短证明（"Simple analytic proof of the prime number theorem", 1980）
