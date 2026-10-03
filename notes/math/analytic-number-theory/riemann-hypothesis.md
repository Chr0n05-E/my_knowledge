---
id: math/analytic-number-theory/riemann-hypothesis
title: 黎曼假设
type: concept
parents: [math/analytic-number-theory]
aliases: [Riemann Hypothesis, RH, 黎曼猜想]
tags: [数论, zeta函数, 未解决问题]
status: growing
created: 2026-10-03
updated: 2026-10-03
---

# 黎曼假设

## 定义

$\zeta(s)$ 经解析延拓后，其全部非平凡零点都位于临界线 $\operatorname{Re} s = \tfrac{1}{2}$ 上。

等价形式（更贴近"素数分布"的形式）：

$$\pi(x) = \operatorname{li}(x) + O\!\left(\sqrt{x}\,\ln x\right),$$

即素数计数函数的误差项被压到"最规则"的量级。

## 我的理解

我第一次看这个猜想时的困惑是：**凭什么零点都在一条竖直线上？** 后来想明白，这条线的位置不是美学偏好，而是函数方程的必然：

$$\zeta(s) = 2^s \pi^{s-1}\sin\!\left(\frac{\pi s}{2}\right)\Gamma(1-s)\,\zeta(1-s).$$

函数方程给了关于 $\operatorname{Re} s = \tfrac{1}{2}$ 的对称性。实轴上那些平凡零点（$s = -2, -4, \dots$）好理解；非平凡零点是"成对"出现的，一对的乘积在对称下被锁在 $1/2$ 这条轴上——如果它们非要成对，那么"都在轴上"是**最对称的可能**，而"偏离轴"是被允许但看起来毫无理由的例外。RH 说的就是：不存在这种例外。所以我把它理解为**一条关于对称性的断言**，而不是一个算出来的数值事实。

第二个理解更实用：RH 与 [[math/analytic-number-theory/prime-number-theorem|素数定理]] 是同一件事的两个精度档位。PNT 只要求 $\zeta$ 在 $\operatorname{Re} s = 1$ 上无零点，于是得到 $\psi(x) \sim x$；RH 要求零点都退到 $1/2$ 线上，于是得到误差项 $O(\sqrt{x}\ln x)$——正好是"素数计数里能被允许的最小随机涨落"的量级（随机模型给出的下界）。换句话说：**PNT 说素数分布有规律，RH 说这个规律好到极限。**

## 直觉 / 为什么

- 显式公式：$\psi(x) = x - \sum_\rho \frac{x^\rho}{\rho} - \ln 2\pi - \tfrac{1}{2}\ln(1 - x^{-2})$。素数的"涨落"就是零点 $\rho$ 贡献的振荡项。零点离临界线越远，振荡的幅度越大（$|x^\rho| = x^{\operatorname{Re}\rho}$）。
- 所以 RH 的几何含义是：**素数分布的误差项完全由零点的位置决定**，而"零点都在 1/2 线上"意味着误差项以 $\sqrt{x}$ 为上界。
- 数论里大量定理是"若 RH 成立，则……"的形式——它像一个总开关，按下它许多估计精度立刻提升一个量级。

## 关键结论

- 已知：$\zeta$ 的临界带内已有超过 $40\%$（近年结果继续提高）的非平凡零点被验证落在临界线上（Levinson、Conrey、Pratt 等逐步推进）。
- 已数值验证：前 $10^{13}$ 量级的零点全部在线上（此数量级随计算进展增长）。
- 等价推广：广义黎曼假设（GRH，对 Dirichlet L-函数）、函数域上的 RH **已被证明**（Weil 对曲线的情形）——"函数域版本成立"是支持 RH 的最强证据之一。
- 反面警示：Mertens 猜想（一个"顺理成章"的界）被 Odlyzko–te Riele 证伪，说明**小样本与直觉都不足以支撑这类断言**。

## 边界与反例

- RH 与"是否存在更深的算术结构"无关：它只是 $\zeta$ 的零点位置问题；不要把它当成能直接推出哥德巴赫猜想的工具（两者有联系但不等价）。
- 常见误解：以为 RH 已经被"几乎证明"。**没有。** 等价形式被提出过很多（如 Nyman–Beurling 判据、Li 判据），但都是把难度平移，而不是降低。
- Cramér 模型给出的素数间隙猜测依赖 RH 式的假设；把模型结论当作定理是经典错误。

## 与其它概念的关系

- 属于：[[math/analytic-number-theory|解析数论]]
- 推广自：[[math/analytic-number-theory/prime-number-theorem|素数定理]]（PNT 是"零阶"结论，RH 是把误差项也管住的加强）
- 前置：$\zeta$ 的解析延拓与函数方程、Perron 公式（见素数定理笔记）
- 对比：[[math/algebra/linear-algebra|线性代数]] 那种"有限维、可完全算清"的对象——RH 属于"无穷、只能估计"的世界，两边的证明技术没有交集

## 未解决的问题

- 我想弄懂"零点分布与随机矩阵（GUE）统计吻合"这件事到底说了什么——Montgomery–Odlyzko 的配对相关猜想与 RH 之间是启发关系还是蕴含关系？
- 函数域上的证明（Weil）为什么不能照搬到数域？卡在哪一步？

## 参考

- Riemann, "Über die Anzahl der Primzahlen unter einer gegebenen Größe"（1859，原文很短，值得读一遍）
- Edwards, *Riemann's Zeta Function*（显式公式与函数方程的经典处理）
- Conrey, "The Riemann Hypothesis"（*Notices of the AMS*, 2003，综述性质）
