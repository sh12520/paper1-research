# 论文 1 独立学术审查

本轮读取导师审阅稿、交接和质量审计，沿冻结参考实现复查公式、控制流与证书，并从封存 CSV 重算开发数字。全文按独立复核结果修订。采用通讯、合成与统计三个视角，下面的局部记录保留每项 Major 的位置、原文、证据、实际改写和状态。相同问题出现在多个视角时，保留不同证据和检查义务。

**审查意见：收窄主张后可提交导师审阅。** 论文的独立领域贡献是把通信服务的状态、时段、执行角色和资源替代写入有限合同语义，并用这些语义约束精确有序的无图候选生成。开发集支持这一实现上的效率差异。通用 best-first、抽象解释、语义归并、有序枚举以及意图替代协商都有已有工作。当前只与一个同域实现的强通用合成基线做主要方法比较。A4 给出原实现中保留精细包络信息的边际作用，单因素试验无法分解交互贡献。 [修订稿](PAPER1_REVISED_AFTER_INDEPENDENT_REVIEW.md) · [最终复核](FINAL_ACADEMIC_REVIEW_REPORT.md)

数学复核把原始能力资格、V3 语义、V4 公开可行和 V5 接受分开。构造器上下文同余、binary64 下界与严格并列次序得到显式前提和论证。独立证明复核共享冻结公共语义，独立重建前沿覆盖。其范围是固定开发查询，未外推为所有文法、实例或实网验证。

仍需补足的主要证据为正式独立确认、对其他强合成架构的外部比较、实际通信测量和真实履约。补足物理时延、排队、并发或策略性谈判需要新的研究设计。本轮保留现有数学与工程范围，未修改模型、算法、试验数据或冻结候选。 [人工审批事项](HUMAN_APPROVAL_ACTIONS.md)

## 创新性、通信领域与引文独立复核

### Major L1　协商、意图生成与标准关系

- **位置与原表述**：§2.1 以 RFC 9315、3GPP TS 28.312、Marsico 等和 Mostafa 等定位研究，概括 Marsico 为「允许网络寻找替代供给方案」，未对比资源受限时直接生成备选意图的同行工作。§2.2 只把 Merlin 的相关能力概括为供给、编译和委派核查。
- **问题与证据**：Sharma 等直接处理用户与服务提供者意图冲突，在有限物理／虚拟资源上找备选意图，再由提出方接受或拒绝。3GPP TS 28.312 V19.5.0 §4.6.2–4.6.3 已定义预评估和履约协商，包括可行性、可履约结果、偏好反馈等，附录 H 还描述效用。Merlin §4 的运行时 negotiators 修改和验证委派策略。以上重叠足以排除「提出应用与网络意图协商」「首次能力约束备选」等广义主张。本文的双方固定验证／提案协议仅检验候选流能否用于协商，不提供协议级优势或标准一致性证据。 [Sharma 等](https://pure.qub.ac.uk/en/publications/intent-negotiation-framework-for-intent-driven-service-management/) · [3GPP TS 28.312 V19.5.0](https://www.etsi.org/deliver/etsi_ts/128300_128399/128312/19.05.00_60/ts_128312v190500p.pdf) · [Merlin §4](https://www.cs.cornell.edu/~jnfoster/papers/merlin.pdf)
- **修改方案、修改后表述**：补入 Sharma，明确 3GPP 的实际功能，把 Merlin 对照推进到运行时策略变换。§2.1 限定差分为「为有限能力约束的结构合同域提供无需预建图且可独立核验的精确有序候选流」。§1 把双方保留接受与公开排序精确性分开。
- **处置**：相关工作与主张已修正。若正文提出完整意图交互、真实执行或协议创新，仍须另有直接证据。

### Major L2　最接近的程序合成与等价枚举

- **位置与原表述**：§2.3 从 Mell 等的最优程序合成、e-graph 和预存记录的 Top-K 聚合跳到按需结构合同生成，省略了直接研究「按代价有序生成」的先例。§1 把保守界与去重合成一句贡献，容易误读为通用搜索技术的新组合理论。
- **问题与证据**：Bee Search 在可预生成代价下按真实代价有序构造，Eco Search 在该类代价下进一步证明常数生成延迟。BUSTLE 对样例的具体求值做观察等价合并，egg 对给定等式和同余类共享，NetKAT 对网络包程序提供组合语义和完整等式理论。Mell 等允许用户自定义目标的抽象转换，其最优性框架也涵盖非单调目标的保守变换。本文的专门性来自按资源快照求值的合同公开目标、局部时间重基与公开角色成本约束的合同同余，以及保持覆盖的结构—参数归并和精确前缀说明。仅凭目标与语法的差异，不能断言 Bee／Eco 类方法不可改造到同一任务。 [Bee Search](https://www.jair.org/index.php/jair/article/view/14394) · [Eco Search](https://ojs.aaai.org/index.php/AAAI/article/download/34139/36294) · [BUSTLE](https://arxiv.org/abs/2007.14381) · [egg](https://popl21.sigplan.org/details/POPL-2021-research-papers/23/egg-Fast-and-Extensible-Equality-Saturation) · [NetKAT](https://www.cs.cornell.edu/~kozen/Papers/NetKAT.pdf) · [Mell 等](https://www.cis.upenn.edu/~stevez/papers/MZB24.pdf)
- **修改方案、修改后表述**：引入上述参照，§2.3 明示不同搜索任务的代价计算条件，并用「冻结合同签名和上下文条件」描述合同归并。保留通用基线为同域抽象最优搜索思想的强化实现，包含同一公开抽象转移和资源预算、区间界、每单元联合松弛及父界继承。排序按同一公开分数和语义键，不能与文献作者系统性能直接比较。 [本项目基线规格](../PAPER_GENERIC_BASELINE_SPEC.md)
- **处置**：通用 novelty 过界和相关工作缺口已修正。相对于适配后的其他强有序合成方法的普遍优势缺少直接证据，当前实证对象限于已实现的同域对照。

### Major L3　状态—时间—资源包络的可归因程度

- **位置与原表述**：原 §1 把状态—时间—资源包络、下界和结构归并列为贡献。原 §6 将 A4 单独比较作为时空包络效果的证据。
- **问题与证据**：A4 在相同 transfer 后拓宽六个单元信息，保留原能力、合法性和全合同最低组数。它额外支付并集的时间。已封存结果一般支持更细信息能减少展开。原深度共同认证 n=96，拓宽版配对展开差中位数 +197、耗时 +0.02293 s；预定 high-cost n=30 为 +7,790 和 +0.6287 s。结果支持该实现中把精细信息馈给下界的边际作用，不能测出用另一套廉价基础域替换精细 transfer 的直接节省。A2 只切换独立坐标界，与另含联合松弛的强通用对照不同。A3 的公开 capability predicate 主要是求解前硬资格，合法性基于原始派生。A6 改变可共享的规范模板，和 A1 存在交互。 [消融规格](../PAPER_ABLATION_SPEC.md) · [开发比较](../PAPER_DEVELOPMENT_COMPARISON.md)
- **修改方案、修改后表述**：§1 和 §2.3 将包络、能力资格和规范化定位为有限合同域的构造和实现；归因按 A4 的定点拓宽、A3 的过滤时机、A6 与归并交互逐项拆开。只将精细抽象带来的工作量变化解释为固定开发实现中的边际证据。
- **处置**：归因边界已明确。若要声称包络的普遍独立效应、跨领域优越性或部署效率，仍需额外独立对照。

### Major L4　标题与 6G 结论范围

- **位置与原表述**：原题「面向6G智能体通信意图协商的能力语义约束按需合同合成方法」。§1 使用 IMT-2030 和工作草案提供 6G 背景。
- **问题与证据**：ITU-R M.2160-0 说明远期场景和能力愿景，Liang 与 Yu 是个人工作草案。RAN/FH/EDGE 在本项目中是合成的离散容量及资源计账，公开时限、速率和负载没有标定到真实端到端时延、前传流量或无线调度。以 6G 系统作为题目前缀会弱化读者对真正可核验对象的判断。合同只是基准状态机上的资源条件和执行计划。 [ITU-R M.2160-0](https://www.itu.int/rec/R-REC-M.2160-0-202311-I) · [个人 Internet-Draft](https://www.ietf.org/archive/id/draft-ly-multi-agent-in6g-00.html) · [模型规格](../MODEL_SPEC.md)
- **修改方案、修改后表述**：采用「面向通信意图协商的能力约束合同按需合成与精确有序枚举」。6G 仅用于长期应用动机。用「离散状态—时间单元」和「抽象执行模型」区分基准验证与真实履约证据。
- **处置**：题目和相关表述已修正。3GPP 接口符合性、真实延迟、跨域部署与履约属于公开限制。

### 原有 18 条引文的复核账本

复核使用发布机构、主办会议、作者文本或作者所在机构档案。识别信息与支持的正文主张逐条核对。发布站受限时，使用可实际读取的第一方作品副本或档案，记录可访问范围。数字卷期与印刷页码以发布元数据为主。复核日为 2026-11-20。

| 原条目 | 核验结果与正文适用性 | 一手来源 |
|---|---|---|
| `itur2023m2160` | Recommendation M.2160-0，2023-11。支持 IMT-2030 场景及通信与 AI、计算卸载的背景；用作愿景文件。 | [ITU-R 正式记录](https://www.itu.int/rec/R-REC-M.2160-0-202311-I) · [正式 PDF](https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.2160-0-202311-I%21%21PDF-E.pdf) |
| `clemm2022rfc9315` | Clemm、Ciavaglia、Granville、Tantsura，2022-10，Informational RFC，DOI `10.17487/RFC9315`。§3、§5 支持声明式意图、转换、编排和保障的区分。 | [RFC Editor 原文](https://www.rfc-editor.org/rfc/rfc9315.html) |
| `3gpp2026ts28312` | ETSI TS 128 312 V19.5.0，2026-04，对应 3GPP TS 28.312 Release 19。§4.6 及附录 H 支持双阶段协商与效用表达的对照。 | [ETSI 历史固定版本](https://www.etsi.org/deliver/etsi_ts/128300_128399/128312/19.05.00_60/ts_128312v190500p.pdf) |
| `liang2026multiagent` | Liang Shuang、Yu Menghan，`draft-ly-multi-agent-in6g-00`，2026-07，个人 Internet-Draft，原文标注 2027-01-07 到期。支持能力暴露和发现作为探索背景。 | [IETF 归档原文](https://www.ietf.org/archive/id/draft-ly-multi-agent-in6g-00.html) · [发布公告](https://mailarchive.ietf.org/arch/msg/i-d-announce/ltu5g7CuUFQWQre1Y95hwaf9bKw/) |
| `smith1980contractnet` | Reid G. Smith，IEEE Transactions on Computers C-29(12)，1104–1113，1980。支持分布式任务分派，DOI `10.1109/TC.1980.1675516`。 | [作者保存的发表全文](https://reidgsmith.com/The_Contract_Net_Protocol_Dec-1980.pdf) |
| `jennings2001negotiation` | Jennings、Faratin、Lomuscio、Parsons、Wooldridge、Sierra，Group Decision and Negotiation 10(2)，199–215，2001。支持对象、协议与决策机制的分层。 | [Springer 发布页](https://link.springer.com/article/10.1023/A%3A1008746126376) |
| `marsico2020automated` | Antonio Marsico、Marco Savi、Domenico Siracusa、Elio Salvadori，Optical Switching and Networking 38，文章号 100571，2020。原文 §3 涉及服务不可供给时受控调整属性、发放替代方案。出版社网页和部分机构下载受限，利用共同作者出版记录与提供的文章文本。 | [作者出版目录第 12 条](https://marcosavi.altervista.org/publications.html) · [作者全文副本](https://www.researchgate.net/publication/341110380_An_Automated_Negotiation_Framework_for_Application-Aware_Transport_Network_Services) |
| `mostafa2024emergent` | Mostafa、ElBamby、Abdel-Aziz、Bennis，ICC 2024，5281–5286，DOI `10.1109/ICC51166.2024.10622580`。对应 QoE 到 QoS／切片的沟通学习，适用于意图翻译对照。 | [作者原稿](https://arxiv.org/abs/2402.02768) · [正式出版 DOI](https://doi.org/10.1109/ICC51166.2024.10622580) |
| `benveniste2018contracts` | Benveniste 等，Foundations and Trends in Electronic Design Automation 12(2–3)，124–400，2018。支持合同组合的通用设计理论，本文未声称实现该元理论。发行站受限，作者机构条目给出文章摘要及 DOI。 | [IST Austria 作者机构记录](https://research-explorer.ista.ac.at/record/5677) |
| `soule2014merlin` | Soulé 等，CoNEXT 2014，213–226，DOI `10.1145/2674005.2674989`。原文 §4 支持带委派验证的运行时协商器。 | [Cornell 作者版全文](https://www.cs.cornell.edu/~jnfoster/papers/merlin.pdf) |
| `alur2013sygus` | Alur 等，FMCAD 2013，1–8，DOI `10.1109/FMCAD.2013.6679385`。支持文法约束与语义规范共同定义的合成。 | [Microsoft Research 作者出版页](https://www.microsoft.com/en-us/research/publication/syntax-guided-synthesis/) |
| `kim2021semgus` | Kim、Hu、D’Antoni、Reps，PACMPL 5 (POPL)，文章 30，2021，DOI `10.1145/3434311`。支持自定义语言语义合成。 | [作者出版全文](https://cseweb.ucsd.edu/~ldantoni/papers/popl21.pdf) |
| `cousot1977abstract` | Patrick Cousot 和 Radhia Cousot，POPL 1977，238–252，DOI `10.1145/512950.512973`。支持抽象解释及其保守近似的理论来源。 | [作者出版目录](https://pcousot.github.io/publications) · [作者扫描本](https://cs.nyu.edu/~pcousot/publications.www/CousotCousot-POPL-77-ACM-p238--252-1977.pdf) |
| `wang2018syngar` | Wang、Dillig、Singh，PACMPL 2 (POPL)，文章 63，2018，DOI `10.1145/3158151`。支持抽象树自动机与精化；其精化机制与本文预先冻结的合同抽象界不同。 | [Microsoft Research 作者出版页](https://www.microsoft.com/en-us/research/publication/program-synthesis-using-abstraction-refinement/) |
| `hart1968astar` | Hart、Nilsson、Raphael，IEEE Transactions on Systems Science and Cybernetics 4(2)，100–107，1968，DOI `10.1109/TSSC.1968.300136`。支持启发式最短路径和可采纳界的搜索基础。 | [原作者 Stanford 档案](https://ai.stanford.edu/~nilsson/OnlinePubs-Nils/PublishedPapers/astar.pdf) · [IEEE 元数据](https://ieeexplore.ieee.org/abstract/document/4082128/authors) |
| `mell2024optimal` | Mell、Zdancewic、Bastani，PACMPL 8 (POPL)，文章 16，刊载页 457–481，2024，DOI `10.1145/3632858`。支持以通用抽象解释构造可采纳界的同域基线。作者投稿 PDF 页码和年份占位，以正式会议及登记信息为准。 | [ACM SIGPLAN 正式会议页](https://popl24.sigplan.org/details/POPL-2024-popl-research-papers/18/Optimal-Program-Synthesis-via-Abstract-Interpretation) · [作者全文](https://www.cis.upenn.edu/~stevez/papers/MZB24.pdf) |
| `willsey2021egg` | Willsey、Nandi、Wang、Flatt、Tatlock、Panchekha，PACMPL 5 (POPL)，文章 23，2021，DOI `10.1145/3434304`。支持同余结构与等式饱和。 | [ACM SIGPLAN 会议页](https://popl21.sigplan.org/details/POPL-2021-research-papers/23/egg-Fast-and-Extensible-Equality-Saturation) · [作者原稿](https://arxiv.org/abs/2004.03082) |
| `fagin2003topk` | Fagin、Lotem、Naor，JCSS 66(4)，614–656，2003，DOI `10.1016/S0022-0000(03)00026-6`。支持已有记录上的有序访问与阈值式 Top-K，与合成未探索语法的证明义务区分。 | [作者全文](https://www.wisdom.weizmann.ac.il/~naor/PAPERS/middle_agg.pdf) · [作者出版目录](https://www.wisdom.weizmann.ac.il/~naor/onpub.html) |

### 新增 5 条引文与引用边界

| 新条目 | 核验与新增用途 | 一手来源 |
|---|---|---|
| `sharma2023intentnegotiation` | Sharma、Bhamare、Kassler、Taheri，IEEE Communications Magazine 61(6)，73–79，2023，DOI `10.1109/MCOM.001.2200504`。明确已有基于资源冲突生成备选意图的同领域先例。 | [作者机构及 DOI](https://pure.qub.ac.uk/en/publications/intent-negotiation-framework-for-intent-driven-service-management/) |
| `anderson2014netkat` | Anderson、Foster、Guha、Jeannin、Kozen、Schlesinger、Walker，POPL 2014，113–126，DOI `10.1145/2535838.2535862`。网络包程序的组合语义与等式完备性先例。 | [Cornell 作者全文](https://www.cs.cornell.edu/~kozen/Papers/NetKAT.pdf) |
| `ameen2023beesearch` | Ameen、Lelis，JAIR 77，1275–1310，2023，DOI `10.1613/jair.1.14394`。在其代价模型中支持精确排序及构造时机这一合成先例。 | [JAIR 出版页](https://www.jair.org/index.php/jair/article/view/14394) |
| `matricon2025ecosearch` | Matricon、Fijalkow、Lagarde，AAAI 39(18)，19432–19439，2025，DOI `10.1609/aaai.v39i18.34139`。常数生成延迟保证限于可预生成代价，本文不借用其复杂度。 | [AAAI 出版原文](https://ojs.aaai.org/index.php/AAAI/article/download/34139/36294) |
| `odena2021bustle` | Odena、Shi、Bieber、Singh、Sutton、Dai，ICLR 2021。样例求值、观察等价和学习引导的程序生成先例。改用作者机构全文和 arXiv 作者稿进行核对，OpenReview 请求遇浏览器验证。 | [作者机构条目](https://research.google/pubs/bustle-bottom-up-program-synthesis-through-learning-guided-exploration/) · [代码作者合稿全文](https://arxiv.org/abs/2007.14381) |

这 23 条来源支持修订稿采用的具体历史与技术对照。参考文献核验判断每条引文能支持什么。它不证明相关工作穷尽、广义首创或独立确认效应。

### 第二遍加入的数值分析资料

Higham（2002），《Accuracy and Stability of Numerical Algorithms》，第 2 版，SIAM，DOI `10.1137/1.9780898718027`。用于 §5.2 的乘积误差记号及有限精度分析框架。CS-ODS 的操作数数量、绝对量上界及安全余量仍由冻结实现和本文推导给出。 [SIAM 图书](https://epubs.siam.org/doi/book/10.1137/1.9780898718027) · [第 3 章](https://epubs.siam.org/doi/10.1137/1.9780898718027.ch3)

## 第 3–5 节数学、解释器与正确性复核

接受本节的数学结论以冻结论文域为条件。核查直接沿解释器、签名编码、搜索和证明裁判路径展开，没有采用历史测试通过率代替证明。

### Major M-SEM-1　类型、能力与精确域需要分层

- **章节及原文**　第 3.2–3.3 节，“每个构造器和参数都来自本查询的公开类型域”“对通过相同类型、深度和公开能力前置要求的候选，相等键保留 V2–V5 所需的基准语义”。
- **具体问题**　原文把 V1 的类型检查、原始语法空间的可用产生式，以及规范合同的 V2 绑定混在一起。V1 接受类型正确但不在公开域中的参数。裸 `If(moving,a,a)` 可规范化为 $a$，解释器在规范化后查 V2。若直接据此定义搜索域，缺条件能力的原始树会争夺 $a$ 的字典序见证。V3 的递归有效性也不蕴含 V4 的活动约束。
- **证据**　`src/engine.py::_typed/_required_scopes/_semantic`。`src/state_machine.py::normalize/verify_instance`。`results/grammar_gate/abstract_semantics.py::AbstractSemantics.__init__` 按原始产生式角色筛选。`src/instances.py::hard_check` 与 `config.yaml` 单独要求至少一个活动单元。
- **修改方案**　定义原始域 $\mathcal R_d$、规范结构域 $\mathcal D_d$ 与 V4/V5 分别适用的资格。加入全空闲反例，并记录同查询紧凑键的固定前提。
- **修改后内容**　“一个键的见证取自 $\mathcal R_d(x)$ 中产生该键的原始树，先选最小原始语法键，再将该树规范化。”当可用调度能力时，三重 `Delay(1,·)` 包装仍可通过 V1–V3，随后因无活动单元被 V4 拒绝。
- **状态**　已解决论文定义。冻结的搜索域继续有效。

### Major M-SEM-2　签名相等、上下文同余和见证选择是独立义务

- **章节及原文**　第 5.1 节，“非条件算子依据相同参数选择或搬移相同单元，再合入相同父角色和作用域，整树签名保持不变”。
- **具体问题**　从六个执行单元不能推出未执行分支的 V2 资格。父作用域改变基础角色的 “static” 标记，结构角色的作用域另按引入算子计入。相等签名也不表示原始 AST 深度相同，不能把最小词法见证泛化为任意上下文的合法替代项。
- **证据**　`src/engine.py::_required_scopes` 对 `Static` 用封闭作用域或 `static`。`src/state_machine.py::semantic_key/_predicate/_active_roles` 独立写入全树足迹、V3 有效位及逐单元活动角色。`src/compact_semantics.py::CompactEncoder.pack` 用固定表还原角色声明和成本。
- **修改方案**　逐构造器说明时间传输与作用域变换，交代谓词、V3 和折叠触发条件，保留合法推导前提。另证模板恢复最小原始见证。
- **修改后内容**　“如果 $S$ 为子合同基础角色的所需作用域，父算子作用域为 $\omega$，作用域传递为 $(S\setminus\{\mathrm{static}\})\cup\{\omega\}$。”等签名替换保持父签名，原始深度资格与词法见证按各自规则核验。
- **状态**　已解决限定域证明。生产型注册表、非冻结谓词和任意动态计费需另证。

### Major M-SEM-3　参数对称性需要说明折叠后的 AST 可以变化

- **章节及原文**　第 5.3 节，“在骨架固定时，对配置编号作保持相等关系的注入重命名。它保留条件子签名的相等关系……只改动被观察到的配置字节”。
- **具体问题**　配置重命名可能改变等签名分支的语法序。需要证明换掉被选中的规范 AST 后，外层仍得到同签名，且隐藏相关块总有合法延拓。若仅保留根的活动位置，会漏掉决定内层折叠的已掩蔽值。若仅比较包络，无法证明 completion sets 相等。
- **证据**　`results/depth3/depth_search.py::observed_slots/_compile` 对根及每个原始 IF 分支独立观察，过滤超过公开域大小的分区。`results/grammar_dedup/dedup_search.py::DedupCursor._key/_expand/_witness` 保留可见赋值、隐藏配方与取最小 raw key 的顺序。`results/depth3_proof/symbolic_verifier.py::compile_complete_shape/canonical_witness/assign` 独立重建分区、互异赋值与归并见证。
- **修改方案**　从最内层 IF 归纳，把“键不变”与“AST 不变”区分。写明相同模板的全部配方均有隐藏变量扩展，确认不同模板具体键不交。
- **修改后内容**　“两个子签名相等时，配置的语法序可影响折叠后选中的树，但两个选择给出同一签名，外层传输依据命题 1 得到相同父结果。”
- **状态**　已解决冻结域。不会把此结论推广到按配置个体设置能力谓词或带 profile 相关守卫的语言。

### Major M-SEM-4　重新结合下界的可纳性必须来自数值界

- **章节及原文**　第 5.2 节，“因 $2\gamma_{128}\approx 2^{-45}$，实现使用的 $2^{-38}W$ 余量在该冻结有限域内还覆盖余量求值及最终减法的舍入”。
- **具体问题**　原式没有把分量单调松弛与联合项重新结合分开证明。联合项复用了已舍入资源分量，但仍需说明对单元取最小值不会放大误差、扣减余量本身的舍入不破坏方向。评分不能用 V4 的含附加成本负载替换基础需求。
- **证据**　`results/method_dev_v1/public_search.py::_proxy` 按单元按资源累加基础需求的超限和余量，角色成本单独入项。`results/grammar_gate/grammar_search.py::FlatPublicScore.lower_bound/_cell_value/_score` 实现两种界。`results/depth3_proof/cover_verifier.py::PublicBound` 按冻结定义独立实现复核算术。
- **修改方案**　同顺序分量界用有限正确舍入的单调性证明。联合界先在同一组已舍入输入上建立实数松弛，给两求值树统一的绝对误差上界，再核对向下扣减。统一误差界允许逐单元最小化和边缘/本地模式切换，冻结输入保证幅度界。
- **修改后内容**　“128 上界覆盖冻结实现中的顺序累加、除法和计权，每种组合的统一绝对误差不因取最小值而放大。”有限域尺度 $W$ 的安全剩余大于两求值树、微小次正规误差和最终减法误差。
- **状态**　已解决冻结 binary64 路径。未承诺任意浮点平台、求值重排、负成本或扩张参数尺度。

### Major M-SEM-5　原生停止声明需要独立前沿覆盖且同分不能剪

- **章节及原文**　第 3.3 节，“输出携带排序和覆盖证书”。第 5.3 节，“开放和完成堆皆空才证明穷尽”。
- **具体问题**　单一 frontier minimum 或私有封存摘要都不能证明原始根全覆盖。相等下界仍可能产生同分排名更前的键，或产生可改变同键原始见证的推导。预算打断时的半展开状态不能当作穷尽。独立性也不表示没有共享可信语义代码。
- **证据**　`results/depth3/depth_search.py::DepthCursor.next_contract/_frontier_lb` 保留在途下界，开放下界等于缓冲最小分数时继续展开。`results/depth3_proof/symbolic_verifier.py::RootCoverage.skeletons/assign`、`verify_symbolic` 从根重建参数覆盖，逐一复核声称的下界、精确分数位、代表和严格截止。`prepare_holdout_proof_entry.py::refine_depth3` 在独立证明阶段前保存原生在线度量。
- **修改方案**　明确原生记录与独立复核的两个状态；精确发射和短域穷尽分开；限定独立性为独立根覆盖、独立下界实现、排序边界和代表检查。
- **修改后内容**　“完整前缀允许缓冲中保留严格后序的同分候选，开放区域的下界则必须严格超过截止分数。”短域须证明开放、在途和剩余缓冲为空。
- **状态**　已解决论文表述。开发证书通过是固定查询证据，未替代未来持出复核。

### Major M-SEM-6　协商、Nash 和网络执行结论超出验证边界

- **章节及原文**　第 4.3 节，“公共验证器按最多 16 项的批次做精确 V1–V4 检查”“达成一致后，原协议重算规范代表及其公开状态机执行轨迹。”第 3.2 节，“原日志列名为 Nash”。
- **具体问题**　批适配器承接来自合法候选流的 V1 资格，算法并未对每个候选重新解析并运行整个解释器。协议的有限提议、响应、跳过和接受足以定义基准双边协商，但不提供策略、隐私、社会福利最优或真实 6G 履约保证。`Nash` 列是原始接受效用乘积，未扣除分歧效用。时限作为应用配置和验收参数，并不从物理模型推导。
- **证据**　`results/grammar_gate/protocol_adapter.py::_bind_batch/check/run_protocol/reference_utilities`。`results/method_dev_v1/private_protocol.py::negotiate`。`src/instances.py::demand/hard_check/utilities`。`src/state_machine.py::verify_instance`。
- **修改方案**　如实描述 V1 承接、V2–V4 批核验、获胜见证的完整解释器回放和后验 V5 对照。明确总验证预算包含 B2，公共 Top-K 与协议停止分开。解释时限、负载和效用的抽象。
- **修改后内容**　“私有反馈可决定何时停止请求候选，候选顺序仍完全由公开分数和规范键决定。”效用乘积在文中只用来描述已经接受的结果。
- **状态**　已解决原稿实现描述及结论边界。真实网络部署与策略性质保留为后续研究问题。

### Major M-SEM-7　运行规模复杂度与图独立性需要限定

- **章节及原文**　第 5.4 节，只给可实例化分区上界和每次堆操作开销。
- **具体问题**　计算实现仍逐项考察全部受限增长串后才剔除过多块数，不应把 $\sum_{i\le P}S(m,i)$ 当作时间上界。堆复杂度不覆盖分区成本、包络、状态合并、bitwise 评分和词法见证回放。“无图”不意味着最坏成本随目标 $K$ 线性，也不表示内存只随前沿。
- **证据**　`results/depth3/depth_search.py::_compile/next_contract`。`results/grammar_dedup/dedup_search.py::partitions/_witness`。`results/grammar_gate/abstract_semantics.py::AbstractSemantics.__init__` 的稠密 $2^{12}$ 角色表。
- **修改方案**　分别给出原始语法数、带参骨架数、所考察分区、可实例化分区、可见块赋值及真实运行成本项目。
- **修改后内容**　“若骨架有 $m$ 个相关位置，枚举程序最多考察 $B_m$ 个相等分区。”同时说明松下界或大量同分可能迫使多量遍历。
- **状态**　已解决复杂度表述。深度 1–3 的开发结果不承诺更高深度或更大能力表。

## 通信领域与主张外推

### Major C1 · 题目许诺的技术范围（标题、摘要、§1 和 §7.3）

- **原始表述**：“面向6G智能体通信意图协商的能力语义约束按需合同合成方法”。英文题目明确写作 “in 6G Networks”。
- **具体问题**：论文具备真实的通信问题结构。RAN、前传与边缘计算分别占用容量，服务目标和资源成本分别由应用与网络方判断。原题仍容易被读作特定无线代际上的协议或部署成果。六个抽象单元没有空口、流量调度、前传拓扑、传输控制或网络实测。
- **证据**：`src/instances.py:131` 构造归一化容量；`src/instances.py:176` 定义需求；`src/state_machine.py:173` 以后在每个时间和公开状态上独立执行；ITU-R M.2160 是 IMT-2030 的框架与总体目标，3GPP TS 28.312 给出了移动网意图驱动管理和意图协商。 [ITU-R M.2160](https://www.itu.int/rec/R-REC-M.2160-0-202311-I) · [ETSI 版 3GPP TS 28.312，Release 19](https://www.etsi.org/deliver/etsi_ts/128300_128399/128312/19.03.00_60/ts_128312v190300p.pdf)
- **修改方案**：缩小题目到有限合同生成，保留 IMT-2030 的动机和应用语境，区分声明式意图与生成后的执行合同。
- **修改后内容**：“面向通信意图协商的能力约束合同按需合成与精确有序枚举”。§7.3：“测量不涉及标准接口的互通、无线链路性能或 6G 部署。”
- **状态**：论文表述已修订。实网和标准接口证据仍需独立验证，属于研究者决定是否立项的外部效度限制。

### Major C2 · 档位、资源耦合与三种时间含义（§3.1 和 §7.3）

- **原始表述**：“RAN、FH 和 EDGE 使用归一化能力需求与容量刻画资源相互作用。”原文把公开时延档位、时间构造器和搜索耗时放在不同章节，缺少模型内是否相互耦合的说明。
- **具体问题**：若把时延档位当成物理网络时延，读者会误以为拥塞或卸载产生的端到端时延已经量化。当前每个单元按快照重新装入容量，状态也不具备随机轨迹或跨时间排队。应用侧保留效用把档位作为偏好，V4 比较档位上限。
- **证据**：`src/instances.py:176–192`，`src/state_machine.py:180–205`，`results/method_dev_v1/public_search.py:88–107`。基础需求按本地/卸载分别为 $(q,0.4r,0)$ 与 $(0.5q,0.28r,0.5q)$，另有角色负载。FLAT 的基础资源缺口和裕度不直接读时延档位，档位仍可改变归一化和规范键。
- **修改方案**：区分时延档位、启用时间槽和以毫秒/秒报告的程序时钟。说明公开运动状态的容量情景与排队、跨合同竞争的缺席。
- **修改后内容**：“时延档位未由链路、调度、排队或卸载传输时间推导，也未直接进入固定归一化单元布局下的 FLAT 资源缺口与裕度计算。`Delay` 记录业务启用的离散时段。论文另外报告的毫秒和秒是搜索运行时间。”
- **状态**：解释已修订。若要声称时延 QoS 或实际资源效应，须由研究者另决定物理模型和独立评估。

### Major C3 · 协商、信息和履约主张（§3、§4.3、§7.2–7.3）

- **原始表述**：“本文的私有输入隔离限定于生成器和双边接受接口……双边报价与接受协议在本文中作为固定消费者，用于观察精确合同流如何接入协商。”原证据表只给出回放和模拟器的一致性。
- **具体问题**：确定性应用和网络代理与私有偏好阈值在抽象模型下足以描述双边交换。它们无法支持激励相容、策略鲁棒、隐私保证、分布式真实履约或对协议终局达成率的独立性能贡献。公开精确证书也不意味着候选通过后续容量和接受测试。
- **证据**：`src/state_machine.py:143–229` 有 V1–V5 的不同拒绝层；`results/grammar_gate/protocol_adapter.py` 中协议消费已供应的公开候选前缀；RFC 9315 §5 将实现和服务保障分别处理。 [RFC 9315](https://www.rfc-editor.org/rfc/rfc9315.html#section-5)
- **修改方案**：保留作为合同流下游的双边协议，注明信息边界与策略限制，逐层定位资源、接受和证明的含义。与运营层协商工作在 §2 中直接比较。
- **修改后内容**：“生成端仅访问公开记录，接受端按接口使用本方偏好。这是实现级信息边界。交互可能泄露偏好，实验也未涉及策略性代理、谈判均衡、激励相容或开放网络中的协议互操作。” §7.2：“开发数据可以比较生成候选的代价，无法据此主张排序方法提高了相同候选流的协议率。”
- **状态**：修订解决论证范围。协议博弈性质、物理履约与架构安全保留为待评估项。

### Major C4 · OFFLOAD 结构归因与 depth 变化（§7.1）

- **原始表述**：“该类容量构造在所有单元压缩 RAN，而卸载映射降低 RAN 与 FH 的基础需求，并把部分负载移至 EDGE。”原文中的协议存在性归因和按需合成结果紧邻，读者可能把结构域收益归给搜索策略。
- **具体问题**：固定资源反事实中 OFFLOAD 的优势部分来自工作负载设计、资源替代系数和网络效用。辨认出 d3 新语义代表也无法分开深度和机制上限两个因素，更不能推出该实例只有 d3 才能达成协议。
- **证据**：`PILOT_OFFLOAD_ATTRIBUTION.md:5–13` 的 842、783、721、121、F4 229；`config.yaml` 中卸载需求系数；`DEPTH3_NEW_CONTRACT_ANALYSIS.md:40–45,72–78` 的 F3 选择及原 O1 成功。
- **修改方案**：写明分母、反事实集合、基础资源系数、角色附加项、范围限制以及已有协议证据。协议存在性和检索效率分段。
- **修改后内容**：“这些数量描述指定模型中的资源替代和协议存在性。” “扩展设置同时放宽深度和机制组数，观察到的新语义类无法单独归因于深度。”
- **状态**：表述已修订。跨负载泛化和深度独立效应尚未验证，未修改 Frozen 模型或历史归因。

## 实验、对照与统计

### E1 · 共同认证速度比与总体性能（Major，叙述已解决）

**位置与原文。** §6.2 表 2 只展示 96/96 与 92/96 的认证覆盖及共同认证速度比。「这些比值刻画双方已完成的固定配对。全体观察在独立表中保留达限原因、采样内存、实际停点工作量及分母。」

**问题与证据。** 主文图表用的是两种时钟，四条原深度通用路线未认证，Depth 3 有十九条前沿达限。共同认证是受两个方法结果共同决定的筛选子集。Depth 3 只剩五个 27 或 81 类的短域，拿这一组估计两方法在全长 500 上的时延会改变估计对象。配对键 `(instance_id, effective_depth, method, k)` 去重后为 4,800 行。同一有效深度与实例的摘要一致，共同认证的前缀摘要一致。 [封存比较行](../results/paper_method_dev/per_query.csv) · [限额和计时边界](../results/paper_method_dev/run_comparison.py#L85) · [重算记录](work/experiment_recomputed.json)

**修订。** §6.2 将全部配对的双方、仅 CS-ODS、仅通用、双方未认证四格和共同认证时延同表报告；原深度 92/4/0/0、rich-depth2 22/2/0/0、高成本 28/2/0/0、Depth 3 5/19/0/0。并列原深度及 rich-depth2 的总体观察停止时间中位数和 p95，说明停止时钟无法恢复全体查询认证完成时间。开发配对条件估计与预注册的处罚型端点 A 分开。没有用其他模型填补达限后的时延，独立确认仍待运行。

### E2 · 通用基线强度与 Depth 3 正确性证据范围（Major，范围已明确）

**位置与原文。** §6.1「通用对照是同一合同域内的可重复实现」。§6.2「Depth 3 的方法比较使用同查询封存的 CS-ODS 前缀。独立覆盖证书另限于第 6.3 节的 CS-ODS 面板。」

**问题与证据。** 不宜把已实现的一条强通用路线推广成对所有通用合成器的优势，也不能把共同域的前缀比对计为八种 Depth 3 方法各自具有独立覆盖证书。冻结 `GenericCursor` 使用 `mrv` 类型洞分割、父界继承、活动/闲置联合因子界及终端语义去重。`comparable_prefix` 用封存记录核对顺序、binary64 分数位、规范见证、长度与摘要。另有 15 个缩减域全域核对。独立证明 CSV 的 24 个实例仅由 CS-ODS 证据生成，含 62 全长和 10 短域检查点。 [基线实现](../results/paper_method_dev/generic_search.py#L148) · [封存参照比较](../results/paper_method_dev/run_comparison.py#L334) · [基线正确性报告](../PAPER_BASELINE_CORRECTNESS_REPORT.md) · [证明档](../results/depth3_proof/per_query.csv)

**修订。** §6.1 将对照明确为 Mell 等思想在本文 DSL 的一次强同域实现，A2 只换为坐标界，完整通用基线有联合因子界。§6.3 明确独立覆盖证明的 72 个检查点仅计 CS-ODS。性能结论限定于冻结的通用基线与测量条件。通用搜索家族的普遍优势与未见查询性能仍未建立。

### E3 · 协商重放的一致性和可观察性（Major，叙述已解决）

**位置与原文。** §6.2「同前缀输入下的 1,248 条协议重放记录逐字段一致。」

**问题与证据。** 闭环协议的结果证据不能以重放对象一致的数量替代。`replay` 接收前缀和穷尽标志。前缀用完且没有全域穷尽标志时，会报告 `INSUFFICIENT_PREFIX` 或尝试缩到受支持预算。`research_protocol` 为一致性比较剔除耗时并将 JSON 传输产生的预算键统一为字符串。相等的空结果同样记作 `protocol_prefix_match=True`。CSV 重算为 784 全预算、418 部分、46 无可交付结果。在 418 中，412 条最高 B=500，6 条最高 B=100。日志 `nash` 是 $u_Au_N$。 [重放与比较函数](../results/paper_method_dev/run_comparison.py#L191) · [效用乘积的归档计算](../results/grammar_gate/protocol_adapter.py#L237) · [重算记录](work/experiment_recomputed.json)

**修订。** §6.2 使用「同一前缀及穷尽标志的参照重放」并分列可支持的预算档。46 条在主文明确未交付协议结果。公开检索时钟从协议中分列，协议输出一致不能推出更高协议率。

### E4 · 消融的指标交互及 A5 截尾（Major，归因已收窄）

**位置与原文。** §6.4「在 30 个高成本开发查询的共同交付配对中，A1、A2 和 A4 增加的展开次数中位数分别是 351、1,246 和 7,790。」A5「继续至穷尽的最终交付分别为 66/96 与 5/24」。

**问题与证据。** 表中的非完整交付混有首次证书已有但继续预算耗尽。按 `prefix_status` 和 `delivery_status` 分别重算，A5 首次认证为 96/96、24/24，只有 66/96、5/24 在继续后穷尽。A4 在继承的精细包络上对各单元取并集，保留精细转移的运行成本。A6 延迟规范化，影响早期等价分区可共享的表示。单项改动不能推出模块的可加、相互独立或通用因果贡献。A3 的九条原深度展开达限不能被 rich-depth2 的零展开差掩盖。 [消融实现](../results/paper_method_dev/ablations.py) · [A5 后续循环](../results/paper_method_dev/run_comparison.py#L141) · [全部消融分母](../PAPER1_FINAL_DELIVERY/PAPER1_TABLES/ablation_k500_summary.csv)

**修订。** §6.4 列出六项消融的首次证书覆盖及各种达限，A5 分列证书后穷尽和截尾。注明 A4 衡量精细信息对下界收紧的边际作用，A6 和早期去重可能交互。A6 的 1,647 个额外展开及 0.507 s 只对应 28 个共同认证高成本配对。A5 截尾增量只取下界，未外推完成时间。

### E5 · 预建索引的成本分摊（Major，计量边界已解决）

**位置与原文。** §6.5「图构建、序列化统计和 17 个能力索引准备合计 1,154.218 s，两个索引合包新增的构建与序列化量为 20.866 s。」原文将索引暖态查询与冷启动分列，对单树常驻与资产摊销的可辨识边界交代有限。

**问题与证据。** 图索引共享资产且开发暖态将两棵树同时驻留，不能由共同工作集反推出单树峰值。额外 20.866 s 含联合序列化，单树序列化时钟未知。冷启动五次分别对应五种方法的一个 sparse 夹具，文件页缓存未控制。Contract-Aware Index 在完整暖态批次比 CS-ODS 累计少 5.568 s。充分高的资产复用可能摊薄建图成本，不能用图构建时间作普遍在线胜负的依据。 [历史资产阶段与分摊](../PAPER_COST_FAIRNESS_AUDIT.md) · [暖态进程](../results/paper_method_dev/worker_startup.json) · [新进程单夹具](../results/paper_method_dev/cold_start_costs.json)

**修订。** §6.5 分别报告图、能力包、两索引联合资产、单路线资产和 96 个暖态尝试。明确缺失单路线构建与常驻峰值证据，冷启动的单夹具没有可泛化的摊销阈值。在 Depth 3 保留 FLAT 与两索引为 N/A。

### E6 · OFFLOAD 归因与深度新增协议（Major，解释已限定）

**位置与原文。** §7.1「783 个仅允许 OFFLOAD 结构也可达协议，721 个在去掉 OFFLOAD 后失去所有已验证协议」。原稿报告一个 Depth 3 新语义的协议代表，并指出对应原实例已可达协议。

**问题与证据。** 这些数是固定工作负载、冻结资源方程和条件化分母下的空间反事实。对每个实例重算 OFFLOAD-only/CDP 的配对四格得到 102/681/19/40。必要性是 681+40，共 721。充分性是 102+681，共 783。仅在 F4 的 229 条 B2 失败且完整 O1 成功实例中均为必要。Depth 3 固定开发比较 B=5000 有 14 协议、2 穷尽无协议、8 未知，唯一经复核的 Depth 3 新语义代表不属于原 O1 失败实例。642 是在 8 个不同查询中观察的已验证新语义发生数，允许跨实例重复。 [归因逐实例记录](../results/pilot_attribution/per_instance.csv) · [深度扩展协议记录](../results/depth3/new_contract_agreements.csv) · [深度扩展候选记录](../results/depth3/new_contract_candidates.csv)

**修订。** 保持必要、充分和域变化与排序分开。讨论将归因限定在归一化资源负载及选定条件化集合。实际接入、前传、边缘负载、协议与测量在研究范围外，实现的外部有效性有待证据。原始研究数据未动。

### E7 · Held-out 主判据的失败边界与运行状态（Major，设计说明已解决）

**位置与原文。** §6.6「有可核对资源原因的未认证尝试用 12 s 处罚」并报告主判据，没有在同节说明方法归属失败、不可核清信息及查询对独立假设的不同角色。

**问题与证据。** “未认证”包含已核实归属的方法失败及可核实资源达限，也可能来自缺证或无法解释的缺失。后者触发分析阻断，直接给 12 s 会产生伪造通过风险。冻结 Hoeffding 界要求在事先批准的条件下查询对独立。配置内重抽样的单位是整对，bootstrap 属描述性敏感性分析。 [最终预注册](../METHOD_FINAL_PREREGISTRATION.md) · [最终统计实现](../results/method_holdout_readiness/method_statistics.py) · [授权状态](../METHOD_AUTHORIZATION_STATE.json)

**修订。** §6.6 明确 A/B 的配置数、1 ms 下限、12 s 处罚和独立复核要求。写明阻断条件、同实例配对、整对重抽样与 Hoeffding 主判据，并保留 `APPROVAL_PENDING`。两端点没有已观察的确认值或 PASS/FAIL 结果。

### 数字重算收据

读取五个封存的 CSV，不导入任何研究方法或实例生成器。Stdlib 分组与 `statistics.median` 重算原深度、rich-depth2、高成本及 Depth 3 队列的配对覆盖及观察时钟。p95 对排序后的 $(n-1)\times0.95$ 位置线性插值。逐行检查全长结果恰有 K 个，穷尽短域少于 K。输入摘要及精确数值随重算输出保留。 [重算脚本](work/recompute_experiment_review.py) · [重算结果](work/experiment_recomputed.json)
