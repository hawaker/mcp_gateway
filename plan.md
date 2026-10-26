目标是把本系统构建成一个 REST 转 MCP 的中转站，另外附加 GenBI 查数 MCP。

版本
    v1：业务用户、业务系统、绑定、鉴权、REST 工具、创建接口时调试、上游 MCP 代理、MCP 组、转发（Streamable HTTP 与 SSE）、SMTP 配置、按 MCP 组 / 用户组 / 用户把 MCP 链接信息发给终端用户、发信记录查看、业务 token 的 Redis 缓存及查看、调用日志、参照 @modelcontextprotocol/inspector 调试 MCP。
    v2：GenBI 数据源、ask_bi、行列权限。v1 不迁入 tiga 的数据源流程。

账号
    后台管理员使用本系统现有账号，只负责配置。
    业务用户单独建表，是来调用 MCP 的人，不复用管理员的用户、角色、部门。

一 管理员操作流程（v1）
    1 新增业务用户(举例这个其中某个用户叫张三),还有一些扩展信息,比如邮箱,手机号,昵称,是否启用
        可选步骤: 新建业务用户组,可以把几个人分成一组,一个用户可以出现在多个组里
        用户组只决定这批人能被勾进哪些MCP组。同一个人被两个用户组勾进同一个MCP组,成员只算一次
    2 新增业务系统(举例这个业务系统叫OA)
        必填英文编码,例如 oa。创建后不允许修改。上游 MCP 的工具对外名称用它做前缀,v2 的 ask_bi 也用它
        可以填 baseUrl、是否启用
        系统参数可以在鉴权中通过占位符引用
        先声明标识:唯一标识的字段名,以及可选属性名列表。绑定页面只能给这些字段填值
    3 新增绑定,OA和张三绑定
        必填张三在OA的唯一标识,字段名来自第2步
        可选属性按第2步声明的名字填值,并可以单独禁用这条绑定
        一个业务用户可以同时绑定多个业务系统。张三可以既绑定OA又绑定MES,各自一条绑定,标识分开
        同一个人在同一个业务系统里只保留一条绑定
        禁用张三和OA的绑定时,他调用MES不受影响
        他只绑定了OA、再去调用MES的工具时,返回无权限,请求不发到MES
    4 新增业务系统的鉴权(这里以OA为例),需要提供鉴权方法和URL
        每个业务系统同时只有一套启用中的鉴权配置
        不论哪种方法,成功后都收成同一种结构再往下用: access_token、expires_at、token_type
        鉴权 URL 以 http:// 或 https:// 开头就直接用,否则接在该业务系统的 baseUrl 后面
        前三种方法必须同步返回。第4种由用户打开页面完成验证后再拿到 token
        v1不执行管理员提交的js/python。token和有效期各自从响应里取值,来源可以是:
            Header: 填header名。值若带 Bearer 前缀就去掉。Set-Cookie 填cookie名
            JSON body: 填JSON路径,例如 $.data.token
            Form body: 填字段名
            纯文本body: 整段正文就是取值结果
            其他文本(含XML): 一条正则,只使用第一个捕获组,并限制正文长度和匹配时间
        响应里没有有效期时,管理员填一个固定秒数。有有效期时,配置里写明这是绝对时间还是秒数
        暂时只支持以下方法:
        1): 固定接口:把用户在OA的唯一标识,post到url,url返回json,再按上面的取值规则收成统一结构,后续用这个token调用他们的服务接口
        2): 自定义接口:管理员自己填写url,选择请求方法,可以把用户的其他标识和唯一标识通过占位符替换放到请求的param参数,json参数,或者form参数中,再按上面的取值规则收成统一结构
        3): basic auth: 账号密码属于业务系统,不属于个人。管理员在该系统的鉴权配置里填一套账号密码、url、请求方法,及可用的唯一标识和非必填标识占位符,再按上面的取值规则收成统一结构
        4): 交互式验证: OA 需要用户打开页面填写验证码时使用。管理员填写 OA 的验证页面 URL,以及回调后如何按上面的取值规则取出 token
            张三调用 OA 的工具时,Redis 里没有他在 OA 的 token,网关不请求业务接口,生成一条只属于张三的短期验证链接,放进这次 tools/call 的返回里
            张三打开链接,在 OA 页面完成验证码。OA 回到本系统的回调地址后,网关把得到的 token 收成 access_token、expires_at、token_type,写入张三在 OA 的 Redis 缓存
            他再次调用同一个工具时,使用这条缓存,不再打开页面
            链接只对当前 MCP token 对应的用户有效,别人打开无效。验证码过期或填错时停在 OA 页面,工具结果里不带业务 token
            这种方式在缓存缺失或业务接口返回 401 时,不自动重试登录,改为返回新的验证链接
        选择鉴权方法的界面上,四种方法各有一张时序图和一段详细介绍,供管理员决定用哪一种。界面用本项目 frontend 里的组件
            时序图的参与者是:用户的 MCP 客户端、本系统、OA。需要缓存时标出 Redis。第4种再标出用户的浏览器
            介绍写明:适用的 OA 登录方式、管理员要填哪些项、token 何时拿到、用户要不要打开页面、失败时用户看到什么
            固定接口:客户端调用工具后,本系统把唯一标识同步 POST 给 OA,OA 当次返回 token,写入 Redis,再请求业务接口。适合 OA 有固定登录接口且当场返回 token 的情况
            自定义接口:步骤与固定接口相同,请求的方法、参数位置和 token 的取值位置由管理员配置。适合 OA 能同步返回 token,但报文不是固定格式的情况
            basic auth:本系统用业务系统级的一套账号密码向 OA 换 token,不使用张三个人的账号。适合 OA 只认一个服务账号的情况
            交互式验证:第一次调用不请求业务接口,本系统把验证链接返回给客户端;用户在浏览器完成验证码;OA 回调本系统后 token 写入 Redis;用户再次调用才请求业务接口。适合 OA 必须由人打开页面填验证码的情况
    5 新增业务系统服务接口。字段和调用时的参数映射参照 @mcp-context-forge 的「Add New Tool from REST API」,以及 mcpgateway/services/tool_service.py 里 REST 调用的做法。界面用本项目 frontend 里的组件,不搬 context-forge 的 Admin UI
        表单包含:名称、显示名、URL、描述、请求方法、Headers、Input Schema(可用 Schema Builder 或直接填 JSON,含 passthrough)、Output Schema、Json Path Filter
        工具 URL 以 http:// 或 https:// 开头就直接用,否则接在该业务系统的 baseUrl 后面。URL 中的 {参数} 先用 MCP 传入的参数替换。GET 时其余参数进 query,其他方法进 body。配置了 query_mapping 或 header_mapping 时,按 context-forge 的映射规则放进 query 或 header
        业务 token 仍按本方案放到工具配置的位置:某个 Header(默认 Authorization: Bearer {{token}})、Query,或 Body。不在工具上再存一套静态账号或固定 Bearer
        只配置超时,不限制响应体大小
        工具上若配置了 Json Path Filter,先过滤再把结果交给用户
        工具定义可以单独禁用。禁用后,所有引用它的MCP组都从 tools/list 去掉它;tools/call 返回无权限,不刷新业务token,不转发
        创建和编辑这个接口时都可以调试。@mcp-context-forge 的「Add New Tool from REST API」表单本身不能调试,Test Tool 只在工具保存后,从工具列表按 Input Schema 填参数再调用
        本系统在创建表单上就可以调试,不必先保存。管理员选择一个已绑定该业务系统的用户,按当前表单里的 URL、方法、Header、Query、Body 和 Input Schema 填参数
        调试走和第8步 REST 调用相同的占位符、业务 token 刷新和超时。该用户没有绑定或绑定已禁用时,不向业务系统发请求
        页面展示 HTTP status code、发出的请求和响应体。MCP token 不参与这次调试。业务 token 默认遮住,管理员可以展开查看
        这次调试不记入第9步调用日志。界面用本项目 frontend 里的组件
    7 MCP 代理。新增一个 MCP 代理(不挂业务系统),通过本系统代理并控制用户权限
        必填名称与不可变英文编码 code。保存对方的地址和一份凭证。v1 调用始终用这一份凭证,不使用张三的绑定,也不使用他的业务 token
        该代理的 tool 被选进某个 MCP 组,用户在这个组里,并且用户和 MCP 组都未禁用,就可以调用。不检查业务系统绑定,也不刷新业务 token。对方返回 401 时把这次响应交给用户,不重新登录
        从对方拉取工具列表,管理员勾选后,这些工具才能进入第8步
        对方后来新增的工具,默认不放进已经建好的MCP组
        对外名称加上该代理的英文编码前缀,避免和REST工具重名
        调用日志上游调用写 upstream_id,system_id 为空;REST 仍写 system_id
    8 创建MCP组:
        1): 管理员从第5步创建的工具中选择(支持从多个业务系统)。UI上按业务系统分组
        2): 从第7步创建的上游MCP中选择tools。UI上按上游MCP分组
        3): 以上两类至少选一类
        4): 工具属于MCP组。同一MCP组内,工具对外名称不能重复,有重复的让人工起别名
            已选进 MCP 组的工具不能从组里拿掉,只能禁用。要去掉这个工具,在业务系统里删除对应接口。删除后,引用它的 MCP 组不再提供该 tool,调用返回无权限
            上游 MCP 的 tool 同样不能从组里拿掉。在第7步去掉该 tool 或删除该上游 MCP 后,已加入的 MCP 组不再提供它
            同一个人进入多个MCP组时,各组使用各自的地址和token。tools/list只返回当前这条连接所属组的工具,各组之间的同名工具互不影响
        5): 勾选用户组和用户
            已勾选的用户和用户组不能从 MCP 组移出,只能禁用 MCP 组中的该成员,或禁用 MCP 组中已勾选的用户组
            禁用后 MCP 地址和 token 不变,该成员或该用户组覆盖的用户不能调用,返回无权限
            再次启用后,原来的地址和 token 继续有效
            张三若只是因为某个业务用户组被勾选而进入该 MCP 组,离开这个业务用户组后当前不能调用;再加回该业务用户组后,仍使用原来的 MCP 地址和 token
        6): 创建完成后生成该组的MCP地址,并把地址和 token 放进发给该用户的 MCP 链接信息。v1同时支持两种传输,客户端只配置其中一种。两种传输使用同一套 Bearer token、同一套权限,以及同一套 initialize、tools/list、tools/call
            Streamable HTTP: /mcp/{组id}
            SSE: GET /mcp/{组id}/sse 建立事件流,POST /mcp/{组id}/messages 发送消息
            多进程部署时,同一次SSE会话的GET和POST要落到同一进程,或把会话存到共享存储
            按「用户 × 该MCP组」生成token。校验用哈希。另加密保存一份明文,供管理员再次复制和发送。补发不更换 token
            禁用成员、禁用用户组、离开业务用户组后再加回,都不更换地址和 token。只有作废后重发才更换 token。作废重发后,已发出的旧链接失效,需要把新的链接信息再发给用户
            管理员可以让系统按下面三个维度自动发邮件。邮件发到第1步业务用户资料里的邮箱。没有邮箱的用户跳过,并在发信记录里记失败。页面上仍可复制同一份链接信息
            按 MCP 组: 给该组里当前未禁用、且有邮箱的成员各发一封,内容是这个组的地址和该用户自己的 token
            按用户组: 找出这个用户组被勾选且未禁用的各个 MCP 组,给其中未禁用、且有邮箱的用户各发对应组的邮件。一个人属于多个 MCP 组就收到多封,每封对应一个组
            按用户: 该用户未禁用时,给他发送他当前未禁用的各个 MCP 组的链接信息,每组一封。用户已禁用则不发
            用户被禁用,或他在该 MCP 组里被禁用,或他所属的用户组在该 MCP 组里被禁用,都不发这封邮件
            每一封都只包含该用户自己的地址和 token
            链接信息包含该 MCP 组的 Streamable HTTP 地址、SSE 地址,以及请求头 Authorization: Bearer <token>
            发信记录只记用户、MCP 组、途径、成功或失败、时间、失败原因,不记 token 明文
            后台管理员可以查看发信记录,按用户、MCP 组、用户组、成功或失败、时间筛选。列表不展示 token 和 SMTP 密码。业务用户不能查看
            用户把token放在请求头 Authorization: Bearer <token>
            这个MCP里的tool就是本组勾选的tools
        7): 后台监听用户的MCP请求,转发给对应的REST API或上游MCP,并按MCP token做权限校验
            检查MCP token是否存在,找到用户和这个MCP组
            检查用户未禁用,MCP组未禁用,请求的tool属于该组且未禁用
            在某个MCP组内禁用一个tool时,只影响该组。该组地址和用户的MCP token仍然有效,同组其他tool照常调用
            该组的 tools/list 不再返回这个tool。tools/call 在校验阶段直接返回无权限,不刷新业务token,不转发
            调用日志记一条失败:用户、MCP组、工具名、失败,没有上游状态码
            另一个MCP组若仍勾选且未禁用该tool,不受影响
            REST 工具还要检查业务系统未禁用,该用户在该业务系统的绑定存在且未禁用
            REST 工具的业务系统 token 缺失或过期时,先调用该系统的鉴权接口。同一用户、同一业务系统的刷新要加锁,避免并发打出多次登录。拿到 token 后,放到该工具配置的占位符位置,再请求业务接口
            REST 调用时,缓存未过期但业务接口返回 401: 前三种鉴权删掉该用户在该业务系统的这条 Redis 缓存,重新登录并重试一次。第二次仍失败,就把这次响应交给用户,不再循环登录。第4种交互式验证不自动重试,删掉缓存并在工具结果里返回新的验证链接
            上游 MCP 不检查业务绑定,也不刷新业务 token。用户在该 MCP 组里,且用户、MCP 组和该 tool 都未禁用,就用第7步的凭证转发
            业务系统token缓存在Redis,不写入调用日志,也不和MCP token存在同一处
            键是「用户 + 业务系统」。值是 access_token、expires_at、token_type,过期时间跟 expires_at
            张三在OA和在MES是两条缓存。他进入多个MCP组时,这些组里的OA工具共用他在OA的这一份token
            刷新锁也在Redis,键同样是「用户 + 业务系统」。多进程下任意一个进程都能读到同一份token
            上游 MCP 转发时取出用户传入的参数,用第7步保存的那一份凭证向真实 MCP 发请求。对方返回 401 时把这次响应交给用户,不重新登录
            权限校验失败时返回无权限,响应里不带业务系统token
            请求已经发到上游时,把上游响应交给用户。工具配置了 Json Path Filter 时先过滤。调用日志记录 HTTP status code
    9 监控,参照 @mcp-context-forge 目录里这个项目的 监控 -> 指标
        每次 tools/call 记一条调用日志:用户、MCP组、工具、业务系统、耗时、成功或失败、HTTP status code
        请求体、响应体、MCP token、业务系统token默认不入库
        图表只聚合这张调用日志。可以查每个用户访问每个tool的次数和时间
    10 查看业务系统token缓存
        后台管理员可以按业务用户、业务系统查看Redis里当前缓存的 access_token、expires_at、token_type,以及是否已过期
        没有缓存时列表为空
        业务用户不能查看。调用日志仍然不记录token
    11 SMTP。本系统 backend 目前没有邮箱连接配置,v1 补上
        后台管理员配置: 是否启用、SMTP 主机、端口、账号、密码、发件人地址、发件人名称、加密方式(无 / STARTTLS / SSL)
        密码加密保存。发信记录和调用日志都不记密码
        可以发一封测试邮件,确认连接可用
        未启用或配置不完整时,不能按第8步发 MCP 链接邮件。页面复制链接信息仍然可用
    12 调试 MCP。交互参照 @modelcontextprotocol/inspector 的连接、Tools、Protocol、Network。界面用本项目 frontend 里的组件。后台管理员使用,业务用户不能打开
        可以调试两个对象:
            本系统的某个 MCP 组: 选择这个组和一个业务用户,用该用户的 MCP token 连接该组地址。传输选 Streamable HTTP 或 SSE
            第7步的上游 MCP: 用保存的那一份凭证连接对方地址
        连接后执行 initialize,并展示服务器信息
        Tools: tools/list 列出工具、描述和 Input Schema。按 Schema 填写参数,执行 tools/call,展示返回内容
        Protocol: 展示 JSON-RPC 请求和响应
        Network: 展示 HTTP status code、请求头和响应体。SSE 与 Streamable HTTP 都要能看
        调试本系统 MCP 组时,走第8步的同一套权限、业务 token 刷新和转发,并记入第9步调用日志
        Protocol 和 Network 里的 MCP token、业务 token 默认遮住,管理员可以展开查看
        v1 不调试 stdio。调试页不包含 Inspector 的 prompts、resources

占位符
    系统参数、用户标识、业务token使用固定名字,避免互相覆盖:
        {{system.xxx}} 系统参数
        {{user.uid}} 用户在该业务系统的唯一标识
        {{user.attr.xxx}} 绑定上的可选属性,xxx必须是第2步声明过的属性名
        {{token}} 业务系统token
    这些值只来自配置和绑定,不从MCP调用参数里取

二 v2
    1 新增GenBI连接,参照 ./../tiga_case (以下简称tiga_case) 知识中心 -> 系统设置 -> 商业智能 -> 新建数据源,把后续流程迁入本项目
        新建的数据源包装成 ask_bi 工具
        默认对外名称是 {业务系统英文编码}_ask_bi
        同一个MCP组里重名时,走v1第8步的同一套人工别名
    2 MCP组在v1的两类工具之外,可以再选数据源(支持多个业务系统)。UI上按业务系统分组
        选了数据源,则把 tiga_case 中的数据源权限配置挪到这个MCP组里,配置行列权限
        至少要有一类工具或数据源

三 v1验收:OA待办
    业务系统英文编码 oa,baseUrl 为OA地址,唯一标识字段名为 user_id
    张三的绑定值是 zhangsan
    鉴权使用固定接口,POST到OA的登录地址,同步返回json,系统收成 access_token、expires_at、token_type
    REST工具 list_todos 调用OA的待办查询接口,token放在请求头 Authorization: Bearer {{token}}
    MCP组「办公」的 Streamable HTTP 地址是 /mcp/{组id},SSE 地址是 /mcp/{组id}/sse 与 /mcp/{组id}/messages。张三持有该组的MCP token,客户端只配置其中一种
    张三的客户端请求头带 Authorization: Bearer <MCP token>,调用 tools/call,名称为 list_todos
    网关确认token、用户、MCP组、工具、OA系统和绑定都有效;OA的业务token缺失或过期时先刷新再请求;把OA返回的待办结果交回客户端
    管理员在调试页以张三的身份连接「办公」组,tools/list 能看到 list_todos,tools/call 能拿到 OA 待办结果
