"""v1 路由总表"""

from fastapi import APIRouter

from app.modules.ai.chat.controller import ChatRouter
from app.modules.common.file.controller import FileRouter
from app.modules.dbconsole.controller import DbConsoleRouter
from app.modules.generator.gencode.controller import GenRouter
from app.modules.genbi.acl.controller import GenbiGroupDatasourceRouter
from app.modules.genbi.datasource.controller import GenbiDatasourceRouter
from app.modules.genbi.project.controller import GenbiProjectRouter
from app.modules.mcp_gateway.auth.controller import BizAuthRouter
from app.modules.mcp_gateway.auth.interactive_controller import InteractiveAuthRouter
from app.modules.mcp_gateway.binding.controller import BizBindingRouter
from app.modules.mcp_gateway.call_log.controller import CallLogRouter
from app.modules.mcp_gateway.mail.controller import MailRouter
from app.modules.mcp_gateway.mcp_group.controller import McpGroupRouter
from app.modules.mcp_gateway.rest_tool.controller import RestToolRouter
from app.modules.mcp_gateway.runtime.debug_controller import McpDebugRouter
from app.modules.mcp_gateway.smtp.controller import SmtpRouter
from app.modules.mcp_gateway.system.controller import BizSystemRouter
from app.modules.mcp_gateway.token_cache.controller import BizTokenCacheRouter
from app.modules.mcp_gateway.upstream.controller import UpstreamRouter
from app.modules.mcp_gateway.user.controller import BizUserGroupRouter, BizUserRouter
from app.modules.monitor.cache.controller import CacheRouter
from app.modules.monitor.health.controller import HealthRouter
from app.modules.monitor.online.controller import OnlineRouter
from app.modules.monitor.server.controller import ServerRouter
from app.modules.ops.ssh.controller import SshRouter
from app.modules.system.auth.controller import AuthRouter
from app.modules.system.dept.controller import DeptRouter
from app.modules.system.dict.controller import DictRouter
from app.modules.system.log.controller import LogRouter
from app.modules.system.menu.controller import MenuRouter
from app.modules.system.notice.controller import NoticeRouter
from app.modules.system.params.controller import ParamsRouter
from app.modules.system.position.controller import PositionRouter
from app.modules.system.role.controller import RoleRouter
from app.modules.system.ticket.controller import TicketRouter
from app.modules.system.user.controller import UserRouter
from app.modules.system.versions.controller import VersionRouter
from app.modules.task.cronjob.job.controller import CronJobRouter
from app.modules.task.cronjob.node.controller import CronJobNodeRouter
from app.modules.task.storage.browse.controller import StorageBrowseRouter
from app.modules.task.storage.node.controller import StorageNodeRouter
from app.modules.task.storage.transfer.controller import StorageTransferRouter
from app.modules.task.storage.workflow.controller import StorageWorkflowRouter

# 域前缀 → 该域 controller 清单（唯一路由事实来源）
DOMAIN_CONTROLLERS: dict[str, list[APIRouter]] = {
    "/system": [
        AuthRouter,
        UserRouter,
        RoleRouter,
        MenuRouter,
        DeptRouter,
        PositionRouter,
        DictRouter,
        ParamsRouter,
        NoticeRouter,
        TicketRouter,
        VersionRouter,
        LogRouter,
    ],
    "/monitor": [
        CacheRouter,
        HealthRouter,
        OnlineRouter,
        ServerRouter,
    ],
    "/task": [
        CronJobRouter,
        CronJobNodeRouter,
        StorageBrowseRouter,
        StorageNodeRouter,
        StorageTransferRouter,
        StorageWorkflowRouter,
    ],
    "/ai": [ChatRouter],
    "/generator": [GenRouter],
    "/common": [FileRouter],
    "/dbconsole": [DbConsoleRouter],
    "/ops": [SshRouter],
    "/mcp-gateway": [
        BizUserRouter,
        BizUserGroupRouter,
        BizSystemRouter,
        BizBindingRouter,
        BizAuthRouter,
        BizTokenCacheRouter,
        InteractiveAuthRouter,
        RestToolRouter,
        UpstreamRouter,
        McpGroupRouter,
        GenbiGroupDatasourceRouter,
        CallLogRouter,
        SmtpRouter,
        MailRouter,
        McpDebugRouter,
    ],
    "/genbi": [
        GenbiDatasourceRouter,
        GenbiProjectRouter,
    ],
}

api_v1 = APIRouter()
for prefix, controllers in DOMAIN_CONTROLLERS.items():
    router = APIRouter(prefix=prefix)
    for controller in controllers:
        router.include_router(controller)
    api_v1.include_router(router)
