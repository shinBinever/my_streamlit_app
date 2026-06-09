"""
航空部件生命周期与维修管理系统 - Streamlit App
包含数据库连接、7个基础页面和6张高级图表
"""

import streamlit as st
import pymysql
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime

# ============================================================
# 数据库连接配置
# ============================================================
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'wuboxuan031028',
    'database': 'aerospace',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_connection():
    """创建数据库连接"""
    return pymysql.connect(**DB_CONFIG)

def run_query(query, params=None):
    """执行SQL查询并返回DataFrame"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            data = cursor.fetchall()
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame()
    finally:
        conn.close()

# ============================================================
# 存储过程调用函数
# ============================================================

def call_procedure(procedure_name, params=None):
    """通用存储过程调用函数"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.callproc(procedure_name, params or [])
            # 获取第一个结果集
            result = cursor.fetchone()
            # 消费剩余的结果集
            while cursor.nextset():
                pass
            conn.commit()

            # 确保返回字典格式
            if result is None:
                return {"result": "success", "message": "操作完成"}
            if isinstance(result, dict):
                return result
            # 如果是元组，转换为字典（根据存储过程的返回字段）
            if isinstance(result, tuple) and len(result) >= 2:
                return {"result": str(result[0]) if result[0] else "success",
                        "message": str(result[1]) if len(result) > 1 else "操作完成"}
            return {"result": "success", "message": "操作完成", "data": result}
    except pymysql.Error as e:
        conn.rollback()
        raise BusinessError(str(e))
    finally:
        conn.close()

class BusinessError(Exception):
    """业务规则异常"""
    pass

def add_component(serial_number, model_id, batch_no=None, production_date=None, entry_date=None):
    """调用 sp_add_component 存储过程"""
    return call_procedure('sp_add_component', [serial_number, model_id, batch_no, production_date, entry_date])

def install_component(component_id, aircraft_id, position, install_time, operator_id=None, install_reason='安装'):
    """调用 sp_install_component 存储过程"""
    return call_procedure('sp_install_component', [component_id, aircraft_id, position, install_time, operator_id, install_reason])

def remove_component(component_id, remove_time, remove_reason, operator_id=None):
    """调用 sp_remove_component 存储过程"""
    return call_procedure('sp_remove_component', [component_id, remove_time, remove_reason, operator_id])

def replace_component(old_component_id, new_component_id, aircraft_id, position, replace_time, reason, operator_id=None):
    """调用 sp_replace_component 存储过程"""
    return call_procedure('sp_replace_component', [old_component_id, new_component_id, aircraft_id, position, replace_time, reason, operator_id])

def register_maintenance(component_id, maintenance_start, maintenance_end, maintenance_type, result, description=None, responsible_technician_id=None):
    """调用 sp_register_maintenance 存储过程"""
    return call_procedure('sp_register_maintenance', [component_id, maintenance_start, maintenance_end, maintenance_type, result, description, responsible_technician_id])

def retire_component(component_id, retirement_date, reason, approver=None):
    """调用 sp_retire_component 存储过程"""
    return call_procedure('sp_retire_component', [component_id, retirement_date, reason, approver])

def add_flight_log(aircraft_id, takeoff_time, landing_time, mission_type):
    """调用 sp_add_flight_log 存储过程"""
    return call_procedure('sp_add_flight_log', [aircraft_id, takeoff_time, landing_time, mission_type])
# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="航空部件生命周期与维修管理系统",
    page_icon="✈️",
    layout="wide"
)

# 设置Plotly默认主题
pio.templates.default = "plotly_white"

# ============================================================
# 侧边栏导航
# ============================================================
st.sidebar.title("🚀 导航菜单")
page = st.sidebar.radio(
    "选择功能页面",
    [
        "🏠 首页",
        "📦 部件管理",
        "🔧 维修管理",
        "📝 飞行日志",
        "🔍 生命周期追溯",
        "📊 统计分析",
        "⚠️ 异常检测",
    ]
)

# ============================================================
# 辅助函数定义
# ============================================================

def get_status_color(status):
    """状态颜色映射"""
    colors = {
        'IN_STOCK': '#4ECDC4',
        'INSTALLED': '#45B7D1',
        'UNDER_REPAIR': '#F6AE2D',
        'RETIRED': '#D64933'
    }
    return colors.get(status, '#888888')

def get_category_chinese(category):
    """部件类别中文映射"""
    mapping = {
        'Engine': '发动机',
        'Landing Gear': '起落架',
        'Avionics': '航电设备',
        'Hydraulic': '液压系统',
        'Electrical': '电气系统',
        'Structure': '结构件',
        'Other': '其他'
    }
    return mapping.get(category, category)

# ============================================================
# 图1: 甘特图 - 生命周期追溯
# ============================================================
def create_lifecycle_gantt(component_id, serial_number):
    """创建生命周期时间线（使用表格替代甘特图，避免plotly兼容性问题）"""

    # 获取安装记录
    install_query = """
        SELECT 
            '安装' as event_type,
            ir.install_time as start_time,
            ir.remove_time as end_time,
            CONCAT('飞机: ', a.registration_number, ' | 位置: ', IFNULL(ir.position, '未知'), ' | 原因: ', IFNULL(ir.install_reason, '未知')) as details
        FROM InstallationRecord ir
        JOIN Aircraft a ON ir.aircraft_id = a.aircraft_id
        WHERE ir.component_id = %s
        ORDER BY ir.install_time
    """
    install_records = run_query(install_query, (component_id,))

    # 获取维修记录
    maint_query = """
        SELECT 
            '维修' as event_type,
            maintenance_start as start_time,
            maintenance_end as end_time,
            CONCAT('类型: ', maintenance_type, ' | 结果: ', result, ' | 描述: ', IFNULL(description, '无')) as details
        FROM MaintenanceRecord
        WHERE component_id = %s
        ORDER BY maintenance_start
    """
    maint_records = run_query(maint_query, (component_id,))

    # 获取退役记录
    retire_query = """
        SELECT 
            '退役' as event_type,
            retirement_date as start_time,
            NULL as end_time,
            CONCAT('原因: ', IFNULL(reason, '未知')) as details
        FROM RetirementRecord
        WHERE component_id = %s
    """
    retire_records = run_query(retire_query, (component_id,))

    # 合并所有记录
    all_records = pd.concat([install_records, maint_records, retire_records], ignore_index=True)

    if all_records.empty:
        return None, "无生命周期数据"

    # 处理时间格式
    all_records['start_time'] = pd.to_datetime(all_records['start_time']).dt.strftime('%Y-%m-%d %H:%M')
    all_records['end_time'] = pd.to_datetime(all_records['end_time']).dt.strftime(
        '%Y-%m-%d %H:%M') if 'end_time' in all_records.columns else '进行中'
    all_records['end_time'] = all_records['end_time'].fillna('至今')

    # 重命名列
    all_records = all_records.rename(columns={
        'event_type': '事件类型',
        'start_time': '开始时间',
        'end_time': '结束时间',
        'details': '详细信息'
    })

    # 返回表格数据，不返回图表
    return all_records, None

# ============================================================
# 图2: 故障集中分析（表格 + 饼图）
# ============================================================
def create_fault_analysis():
    """创建故障集中分析（维修记录表 + 饼图）"""

    query = """
        SELECT 
            mr.record_id,
            mr.maintenance_start,
            mr.maintenance_end,
            mr.maintenance_type,
            mr.result,
            cm.name as model_name,
            c.serial_number,
            t.name as technician
        FROM MaintenanceRecord mr
        JOIN Component c ON mr.component_id = c.component_id
        JOIN ComponentModel cm ON c.model_id = cm.model_id
        LEFT JOIN Technician t ON mr.responsible_technician_id = t.technician_id
        ORDER BY mr.maintenance_start DESC
    """

    df = run_query(query)

    if df.empty:
        return None, None, "暂无维修数据"

    # 时间格式化
    df['maintenance_start'] = pd.to_datetime(
        df['maintenance_start']
    ).dt.strftime('%Y-%m-%d')

    df['maintenance_end'] = pd.to_datetime(
        df['maintenance_end']
    ).apply(
        lambda x: x.strftime('%Y-%m-%d')
        if pd.notna(x) else '进行中'
    )

    # 中文列名
    table_df = df.rename(columns={
        'record_id': '记录ID',
        'serial_number': '部件序列号',
        'model_name': '部件型号',
        'maintenance_type': '维修类型',
        'result': '维修结果',
        'maintenance_start': '开始时间',
        'maintenance_end': '结束时间',
        'technician': '维修人员'
    })

    # 维修类型颜色
    bright_colors = {
        '定期检修': '#6EC6FF',
        '故障维修': '#FF8A80',
        '故障修复': '#FF8A80',
        '大修': '#B388FF',
        '改装': '#69F0AE',
        '例行检查': '#FFD54F',
        'EMERGENCY': '#FF8A80',
        'ROUTINE': '#6EC6FF',
        'OVERHAUL': '#B388FF',
        'INSPECTION': '#FFD54F'
    }

    # 饼图
    type_counts = df['maintenance_type'].value_counts()

    fig_pie = go.Figure(data=[go.Pie(
        labels=type_counts.index.tolist(),
        values=type_counts.values.tolist(),
        hole=0.45,
        marker_colors=[
            bright_colors.get(t, '#80DEEA')
            for t in type_counts.index
        ],
        textinfo='label+percent',
        hovertemplate='%{label}: %{value}次 (%{percent})<extra></extra>'
    )])

    fig_pie.update_layout(
        title='维修类型占比',
        height=380,
        showlegend=True
    )

    return table_df, fig_pie, None


# ============================================================
# 图3: Sankey图 - 状态流转分析
# ============================================================
def create_sankey_diagram():
    """创建状态流转Sankey图"""
    # 获取所有部件当前状态
    status_query = """
        SELECT current_status, COUNT(*) as count
        FROM Component
        GROUP BY current_status
    """
    status_df = run_query(status_query)
    status_counts = dict(zip(status_df['current_status'], status_df['count']))

    # 获取流转记录
    flow_query = """
        SELECT 
            c.current_status as from_status,
            ir.install_time,
            c.component_id
        FROM Component c
        LEFT JOIN InstallationRecord ir ON c.component_id = ir.component_id
        WHERE ir.remove_time IS NULL
    """

    # 简化流转分析
    sankey_query = """
        SELECT 
            'IN_STOCK' as source,
            'INSTALLED' as target,
            (SELECT COUNT(*) FROM InstallationRecord WHERE remove_time IS NULL AND install_time IS NOT NULL) as value
        UNION ALL
        SELECT 
            'INSTALLED' as source,
            'UNDER_REPAIR' as target,
            (SELECT COUNT(*) FROM MaintenanceRecord WHERE component_id IN 
                (SELECT component_id FROM InstallationRecord WHERE remove_time IS NULL AND install_time IS NOT NULL)) as value
        UNION ALL
        SELECT 
            'UNDER_REPAIR' as source,
            'INSTALLED' as target,
            (SELECT COUNT(*) FROM Component WHERE current_status = 'INSTALLED' AND component_id IN 
                (SELECT component_id FROM MaintenanceRecord WHERE result = 'SUCCESS')) as value
        UNION ALL
        SELECT 
            'INSTALLED' as source,
            'RETIRED' as target,
            (SELECT COUNT(*) FROM Component WHERE current_status = 'RETIRED') as value
    """
    flow_df = run_query(sankey_query)

    # 节点映射
    node_labels = ['库存中', '已安装', '维修中', '已退役']
    node_colors = ['#4ECDC4', '#45B7D1', '#F6AE2D', '#D64933']

    # 准备流量数据
    source_idx = {'IN_STOCK': 0, 'INSTALLED': 1, 'UNDER_REPAIR': 2, 'RETIRED': 3}
    target_idx = {'IN_STOCK': 0, 'INSTALLED': 1, 'UNDER_REPAIR': 2, 'RETIRED': 3}

    sources = [source_idx.get(row['source'], 0) for _, row in flow_df.iterrows()]
    targets = [target_idx.get(row['target'], 0) for _, row in flow_df.iterrows()]
    values = [max(int(row['value']), 0) for _, row in flow_df.iterrows()]

    # Sankey图
    fig_sankey = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=node_labels,
            color=node_colors
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values
        )
    )])

    fig_sankey.update_layout(
        title="部件状态流转分析",
        height=450
    )

    # 状态分布饼图
    pie_query = """
        SELECT current_status, COUNT(*) as count
        FROM Component
        GROUP BY current_status
    """
    pie_df = run_query(pie_query)

    if not pie_df.empty:
        status_labels = {
            'IN_STOCK': '库存中',
            'INSTALLED': '已安装',
            'UNDER_REPAIR': '维修中',
            'RETIRED': '已退役'
        }
        pie_df['status_cn'] = pie_df['current_status'].map(status_labels)

        fig_pie = go.Figure(data=[go.Pie(
            labels=pie_df['status_cn'],
            values=pie_df['count'],
            marker_colors=['#4ECDC4', '#45B7D1', '#F6AE2D', '#D64933'],
            textinfo='label+percent',
            hovertemplate='%{label}: %{value} (%{percent})<extra></extra>'
        )])

        fig_pie.update_layout(
            title="当前状态分布",
            height=400,
            showlegend=True
        )
    else:
        fig_pie = None

    return fig_sankey, fig_pie

# ============================================================
# 图4: 雷达图 - 型号可靠性评估
# （已删除详细指标表）
# ============================================================
def create_reliability_radar(selected_models):
    """创建型号可靠性评估雷达图"""

    if not selected_models:
        return None, "请选择至少一个型号"

    # 查询各型号可靠性指标
    query = """
        SELECT 
            cm.model_id,
            cm.name as model_name,
            COUNT(DISTINCT c.component_id) as total_installed,
            COUNT(mr.record_id) as total_maintenance,
            SUM(CASE WHEN mr.result = 'SUCCESS' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN mr.result = 'SCRAP' THEN 1 ELSE 0 END) as scrap_count,
            AVG(c.total_usage_hours) as avg_usage_hours
        FROM ComponentModel cm
        LEFT JOIN Component c ON cm.model_id = c.model_id
        LEFT JOIN MaintenanceRecord mr ON c.component_id = mr.component_id
        WHERE cm.name IN ({})
        GROUP BY cm.model_id, cm.name
    """.format(','.join(['%s'] * len(selected_models)))

    df = run_query(query, tuple(selected_models))

    if df.empty:
        return None, "所选型号暂无数据"

    # ========================================================
    # 数据归一化
    # ========================================================
    def normalize(series, higher_is_better=True):
        if series.max() == series.min():
            return pd.Series([0.5] * len(series))

        normalized = (
            (series - series.min()) /
            (series.max() - series.min())
        )

        return normalized if higher_is_better else (1 - normalized)

    df['maintenance_score'] = normalize(
        df['total_maintenance'],
        higher_is_better=False
    )

    df['usage_score'] = normalize(
        df['avg_usage_hours'],
        higher_is_better=True
    )

    df['scrap_score'] = normalize(
        df['scrap_count'],
        higher_is_better=False
    )

    df['install_score'] = normalize(
        df['total_installed'],
        higher_is_better=True
    )

    df['success_rate'] = df.apply(
        lambda x:
        float(x['success_count']) / float(x['total_maintenance'])
        if float(x['total_maintenance']) > 0 else 0,
        axis=1
    )

    df['success_score'] = normalize(
        df['success_rate'],
        higher_is_better=True
    )

    # ========================================================
    # 雷达图
    # ========================================================
    categories = [
        '维修稳定性',
        '使用时长',
        '低报废率',
        '安装规模',
        '维修成功率'
    ]

    colors = [
        '#FF6B6B',
        '#4ECDC4',
        '#45B7D1',
        '#F6AE2D',
        '#9B59B6',
        '#3498DB'
    ]

    fig_radar = go.Figure()

    for idx, row in df.iterrows():

        values = [
            row['maintenance_score'],
            row['usage_score'],
            row['scrap_score'],
            row['install_score'],
            row['success_score']
        ]

        color = colors[idx % len(colors)]

        fig_radar.add_trace(go.Scatterpolar(
            r=values + [values[0]],
            theta=categories + [categories[0]],
            fill='toself',
            line=dict(
                color=color,
                width=3
            ),
            fillcolor=f'rgba{tuple(list(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.25])}',
            name=row['model_name'],
            hovertemplate=
            '<b>%{fullData.name}</b><br>' +
            '%{theta}: %{r:.2f}<extra></extra>'
        ))

    fig_radar.update_layout(
        title='型号可靠性评估雷达图',
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1]
            ),
            angularaxis=dict(
                tickfont=dict(size=12)
            )
        ),
        showlegend=True,
        height=500,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02
        )
    )

    return fig_radar, None



# ============================================================
# 页面1: 首页
# ============================================================
def page_home():
    st.title("🏠 系统概览")

    # 核心指标卡片
    col1, col2, col3, col4, col5 = st.columns(5)

    # 飞机总数
    aircraft_count = int(run_query("SELECT COUNT(*) as cnt FROM Aircraft").iloc[0]['cnt'])
    col1.metric("✈️ 飞机总数", aircraft_count)

    # 部件总数
    component_count = int(run_query("SELECT COUNT(*) as cnt FROM Component").iloc[0]['cnt'])
    col2.metric("📦 部件总数", component_count)

    # 维修中
    repair_count = int(run_query("SELECT COUNT(*) as cnt FROM Component WHERE current_status='UNDER_REPAIR'").iloc[0]['cnt'])
    col3.metric("🔧 维修中", repair_count)

    # 今日维修
    today = datetime.now().strftime('%Y-%m-%d')
    today_repair = int(run_query(
        "SELECT COUNT(*) as cnt FROM MaintenanceRecord WHERE DATE(maintenance_start)=%s",
        (today,)
    ).iloc[0]['cnt'])
    col4.metric("📅 今日维修", today_repair)

    # 成功率
    total_repair = int(run_query("SELECT COUNT(*) as cnt FROM MaintenanceRecord").iloc[0]['cnt'])
    success_repair = int(run_query("SELECT COUNT(*) as cnt FROM MaintenanceRecord WHERE result='SUCCESS'").iloc[0]['cnt'])
    try:
        success_rate = f"{float(success_repair) / float(total_repair) * 100:.1f}%"
    except:
        success_rate = "N/A"
    col5.metric("✅ 维修成功率", success_rate)

    st.markdown("---")

    # 高级图表替代原有饼图和柱状图
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📊 部件状态分布")
        status_query = """
            SELECT current_status, COUNT(*) as count
            FROM Component
            GROUP BY current_status
        """
        status_df = run_query(status_query)

        if not status_df.empty:
            status_labels = {
                'IN_STOCK': '库存中',
                'INSTALLED': '已安装',
                'UNDER_REPAIR': '维修中',
                'RETIRED': '已退役'
            }
            status_df['status_cn'] = status_df['current_status'].map(status_labels)

            fig_donut = go.Figure(data=[go.Pie(
                labels=status_df['status_cn'],
                values=status_df['count'],
                hole=0.5,
                marker_colors=['#4ECDC4', '#45B7D1', '#F6AE2D', '#D64933'],
                textinfo='label+percent',
                textposition='outside',
                hovertemplate='%{label}: %{value} (%{percent})<extra></extra>'
            )])
            fig_donut.update_layout(
                height=350,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2)
            )
            st.plotly_chart(fig_donut, use_container_width=True)

    with col_right:
        st.subheader("📈 型号分布 Top 10")
        model_query = """
            SELECT cm.name, COUNT(*) as count
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            GROUP BY cm.name
            ORDER BY count DESC
            LIMIT 10
        """
        model_df = run_query(model_query)

        if not model_df.empty:
            fig_bar = go.Figure(data=[go.Bar(
                x=model_df['count'],
                y=model_df['name'],
                orientation='h',
                marker=dict(
                    color=model_df['count'],
                    colorscale='Viridis',
                    line=dict(width=0)
                ),
                hovertemplate='型号: %{y}<br>数量: %{x}<extra></extra>'
            )])
            fig_bar.update_layout(
                height=350,
                yaxis=dict(autorange='reversed'),
                showlegend=False,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # 近期活动
    st.markdown("---")
    st.subheader("🕐 近期维修记录")

    recent_query = """
        SELECT 
            mr.record_id,
            c.serial_number,
            cm.name as model_name,
            mr.maintenance_type,
            mr.result,
            mr.maintenance_start,
            t.name as technician
        FROM MaintenanceRecord mr
        JOIN Component c ON mr.component_id = c.component_id
        JOIN ComponentModel cm ON c.model_id = cm.model_id
        LEFT JOIN Technician t ON mr.responsible_technician_id = t.technician_id
        ORDER BY mr.maintenance_start DESC
        LIMIT 10
    """
    recent_df = run_query(recent_query)

    if not recent_df.empty:
        recent_df['maintenance_start'] = pd.to_datetime(recent_df['maintenance_start']).dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无维修记录")

# ============================================================
# 页面2: 部件管理
# ============================================================
def page_component():
    st.title("📦 部件管理")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["部件列表", "部件入库", "安装记录", "部件安装", "拆卸/退役"])

    # ========== Tab1: 部件列表 ==========
    with tab1:
        st.subheader("部件列表")

        # 筛选条件
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("状态筛选", ["全部", "IN_STOCK", "INSTALLED", "UNDER_REPAIR", "RETIRED"])
        with col2:
            model_filter = st.text_input("型号筛选")
        with col3:
            serial_filter = st.text_input("序列号搜索")

        query = """
            SELECT c.*, cm.name as model_name, cm.category
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            WHERE 1=1
        """
        params = []

        if status_filter != "全部":
            query += " AND c.current_status = %s"
            params.append(status_filter)
        if model_filter:
            query += " AND cm.name LIKE %s"
            params.append(f"%{model_filter}%")
        if serial_filter:
            query += " AND c.serial_number LIKE %s"
            params.append(f"%{serial_filter}%")

        df = run_query(query, tuple(params) if params else None)

        if not df.empty:
            df['entry_date'] = pd.to_datetime(df['entry_date']).dt.strftime('%Y-%m-%d')
            df['production_date'] = pd.to_datetime(df['production_date']).dt.strftime('%Y-%m-%d')
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("未找到符合条件的部件")

    # ========== Tab2: 部件入库 ==========
    with tab2:
        st.subheader("部件入库")

        # 获取型号列表用于下拉选择
        models_df = run_query("SELECT model_id, name FROM ComponentModel")
        model_options = {f"{row['model_id']} - {row['name']}": row['model_id'] for _, row in models_df.iterrows()}

        with st.form("add_component"):
            col1, col2 = st.columns(2)
            with col1:
                serial_number = st.text_input("序列号 *", placeholder="例如: TEST-001")
                model_selection = st.selectbox("部件型号 *", list(model_options.keys()))
                batch_no = st.text_input("批次号", placeholder="例如: BATCH-2024-001")
            with col2:
                production_date = st.date_input("生产日期", value=None)
                entry_date = st.datetime_input("入库时间", value=datetime.now())

            submit = st.form_submit_button("确认入库")

            if submit:
                if not serial_number:
                    st.error("请填写序列号")
                elif not model_selection:
                    st.error("请选择部件型号")
                else:
                    try:
                        model_id = model_options[model_selection]
                        result = add_component(
                            serial_number=serial_number,
                            model_id=model_id,
                            batch_no=batch_no if batch_no else None,
                            production_date=production_date if production_date else None,
                            entry_date=entry_date
                        )
                        st.success(
                            f"✅ {result.get('message', '部件入库成功')}，部件ID: {result.get('component_id', 'N/A')}")

                    except BusinessError as e:
                        st.error(f"❌ 入库失败: {e}")
                    except Exception as e:
                        st.error(f"❌ 系统错误: {e}")

    # ========== Tab3: 安装记录 ==========
    with tab3:
        st.subheader("安装记录")

        install_query = """
            SELECT ir.*, c.serial_number, a.registration_number, a.model as aircraft_model
            FROM InstallationRecord ir
            JOIN Component c ON ir.component_id = c.component_id
            JOIN Aircraft a ON ir.aircraft_id = a.aircraft_id
            ORDER BY ir.install_time DESC
        """
        install_df = run_query(install_query)

        if not install_df.empty:
            install_df['install_time'] = pd.to_datetime(install_df['install_time']).dt.strftime('%Y-%m-%d %H:%M')
            install_df['remove_time'] = pd.to_datetime(install_df['remove_time']).apply(
                lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) else '安装中'
            )
            st.dataframe(install_df, use_container_width=True, hide_index=True)

    # ========== Tab4: 部件安装 ==========
    with tab4:
        st.subheader("部件安装")

        # 获取在库且未退役的部件
        available_df = run_query("""
            SELECT c.component_id, c.serial_number, cm.name as model_name
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            WHERE c.current_status = 'IN_STOCK' AND c.is_retired = FALSE
        """)

        # 获取在役飞机
        aircraft_df = run_query("""
            SELECT aircraft_id, registration_number, model
            FROM Aircraft
            WHERE status = 'ACTIVE'
        """)

        with st.form("install_component"):
            col1, col2 = st.columns(2)
            with col1:
                if available_df.empty:
                    st.warning("没有可安装的部件（需要在库且未退役）")
                    component_options = {}
                else:
                    component_options = {
                        f"{row['component_id']} - {row['serial_number']} ({row['model_name']})": row['component_id']
                        for _, row in available_df.iterrows()}
                    component_select = st.selectbox("选择要安装的部件 *",
                                                    list(component_options.keys()) if component_options else [""])

                position = st.text_input("安装位置 *", placeholder="例如: 左发动机1号位、右机翼2号位")

            with col2:
                if aircraft_df.empty:
                    st.warning("没有在役飞机")
                    aircraft_options = {}
                else:
                    aircraft_options = {
                        f"{row['aircraft_id']} - {row['registration_number']} ({row['model']})": row['aircraft_id']
                        for _, row in aircraft_df.iterrows()}
                    aircraft_select = st.selectbox("选择飞机 *",
                                                   list(aircraft_options.keys()) if aircraft_options else [""])

                install_time = st.datetime_input("安装时间 *", value=datetime.now())

            install_reason = st.text_input("安装原因", placeholder="例如: 首次安装、故障更换", value="安装")

            submitted = st.form_submit_button("确认安装")

            if submitted:
                if not component_select or not aircraft_select or not position:
                    st.error("请填写所有必填项")
                else:
                    try:
                        component_id = component_options[component_select]
                        aircraft_id = aircraft_options[aircraft_select]
                        result = install_component(
                            component_id=component_id,
                            aircraft_id=aircraft_id,
                            position=position,
                            install_time=install_time,
                            operator_id=None,
                            install_reason=install_reason
                        )
                        st.success(
                            f"✅ {result.get('message', '安装成功')}，记录ID: {result.get('installation_record_id', 'N/A')}")

                    except BusinessError as e:
                        st.error(f"❌ 安装失败: {e}")

    # ========== Tab5: 拆卸/退役管理 ==========
    with tab5:
        st.subheader("拆卸/退役管理")

        # 拆卸
        with st.expander("拆卸部件"):
            with st.form("remove_component"):
                # 获取已安装的部件列表
                installed_df = run_query("""
                    SELECT c.component_id, c.serial_number, cm.name as model_name, a.registration_number
                    FROM Component c
                    JOIN ComponentModel cm ON c.model_id = cm.model_id
                    LEFT JOIN InstallationRecord ir ON c.component_id = ir.component_id AND ir.remove_time IS NULL
                    LEFT JOIN Aircraft a ON ir.aircraft_id = a.aircraft_id
                    WHERE c.current_status = 'INSTALLED'
                """)

                if installed_df.empty:
                    st.info("暂无已安装的部件")
                else:
                    component_options = {
                        f"{row['component_id']} - {row['serial_number']} ({row.get('model_name', '')})": row[
                            'component_id']
                        for _, row in installed_df.iterrows()}

                    component_select = st.selectbox("选择要拆卸的部件", list(component_options.keys()))
                    remove_reason = st.text_area("拆卸原因", placeholder="例如: 寿命到限、故障更换等")
                    remove_time = st.datetime_input("拆卸时间", value=datetime.now())
                    operator_id = st.text_input("操作人员ID（可选）", placeholder="留空则使用系统默认")

                    if st.form_submit_button("确认拆卸"):
                        try:
                            component_id = component_options[component_select]
                            operator = int(operator_id) if operator_id else None
                            result = remove_component(
                                component_id=component_id,
                                remove_time=remove_time,
                                remove_reason=remove_reason if remove_reason else "拆卸",
                                operator_id=operator
                            )
                            st.success(f"✅ {result.get('message', '部件拆卸成功')}")

                        except BusinessError as e:
                            st.error(f"❌ 拆卸失败: {e}")
                        except Exception as e:
                            st.error(f"❌ 系统错误: {e}")

        # 退役
        with st.expander("退役部件"):
            with st.form("retire_component"):
                # 获取未退役的部件（在库或已安装）
                active_df = run_query("""
                    SELECT c.component_id, c.serial_number, cm.name as model_name, c.current_status
                    FROM Component c
                    JOIN ComponentModel cm ON c.model_id = cm.model_id
                    WHERE c.is_retired = FALSE AND c.current_status != 'RETIRED'
                """)

                if active_df.empty:
                    st.info("暂无可退役的部件（所有部件均已退役）")
                else:
                    component_options = {
                        f"{row['component_id']} - {row['serial_number']} ({row['model_name']}, 状态:{row['current_status']})":
                            row['component_id']
                        for _, row in active_df.iterrows()}

                    retire_select = st.selectbox("选择退役部件", list(component_options.keys()))
                    retire_reason = st.text_area("退役原因", placeholder="例如: 寿命到限、不可修复损坏等")
                    retirement_date = st.datetime_input("退役时间", value=datetime.now())
                    approver = st.text_input("审批人ID（可选）", placeholder="技师ID")

                    if st.form_submit_button("确认退役"):
                        try:
                            component_id = component_options[retire_select]
                            approver_id = int(approver) if approver else None
                            result = retire_component(
                                component_id=component_id,
                                retirement_date=retirement_date,
                                reason=retire_reason if retire_reason else "退役",
                                approver=approver_id
                            )
                            st.success(f"✅ {result.get('message', '部件退役成功')}")

                        except BusinessError as e:
                            st.error(f"❌ 退役失败: {e}")
                        except Exception as e:
                            st.error(f"❌ 系统错误: {e}")

# ============================================================
# 页面3: 维修管理
# ============================================================
def page_maintenance():
    st.title("🔧 维修管理")

    tab1, tab2 = st.tabs(["维修记录列表", "维修登记"])

    with tab1:
        st.subheader("维修记录列表")

        records_query = """
            SELECT 
                mr.*,
                c.serial_number,
                cm.name as model_name,
                t.name as technician
            FROM MaintenanceRecord mr
            JOIN Component c ON mr.component_id = c.component_id
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            LEFT JOIN Technician t ON mr.responsible_technician_id = t.technician_id
            ORDER BY mr.maintenance_start DESC
        """
        records_df = run_query(records_query)

        if not records_df.empty:
            records_df['maintenance_start'] = pd.to_datetime(records_df['maintenance_start']).dt.strftime('%Y-%m-%d')
            records_df['maintenance_end'] = pd.to_datetime(records_df['maintenance_end']).apply(
                lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else '进行中'
            )

            # 结果颜色
            def color_result(result):
                colors = {'SUCCESS': 'green', 'PARTIAL': 'yellow', 'SCRAP': 'red'}
                return f"background-color: {colors.get(result, '')}"

            st.dataframe(records_df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无维修记录")

    with tab2:
        st.subheader("维修登记")

        # 获取可维修的部件（未退役且当前已安装的部件 - 严格模式）
        available_df = run_query("""
            SELECT c.component_id, c.serial_number, cm.name as model_name, c.current_status
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            WHERE c.is_retired = FALSE 
              AND c.current_status != 'RETIRED'
              AND c.current_status = 'INSTALLED'
            ORDER BY c.serial_number
        """)

        # 获取技师列表
        tech_df = run_query("SELECT technician_id, name, role FROM Technician")

        with st.form("add_maintenance"):
            col1, col2 = st.columns(2)
            with col1:
                if available_df.empty:
                    st.warning("⚠️ 当前没有已安装的部件可以进行维修登记")
                    component_options = {}
                else:
                    component_options = {
                        f"{row['component_id']} - {row['serial_number']} ({row['model_name']})": row['component_id']
                        for _, row in available_df.iterrows()}
                    component_select = st.selectbox("选择维修部件 *", list(component_options.keys()))

                maintenance_type = st.selectbox(
                    "维修类型",
                    ["例行检查", "定期检修", "故障维修", "大修", "改装", "EMERGENCY", "ROUTINE", "OVERHAUL",
                     "INSPECTION"]
                )

                result_type = st.selectbox(
                    "维修结果 *",
                    ["SUCCESS", "PARTIAL", "SCRAP"],
                    format_func=lambda x: {"SUCCESS": "✅ 成功（可继续使用）", "PARTIAL": "⚠️ 部分恢复",
                                           "SCRAP": "❌ 报废"}.get(x, x)
                )

            with col2:
                start_datetime = st.datetime_input("维修开始时间 *", value=datetime.now())
                end_datetime = st.datetime_input("维修结束时间 *", value=datetime.now())

                if tech_df.empty:
                    technician_options = {}
                    st.info("暂无技师数据，可留空")
                else:
                    technician_options = {
                        f"{row['technician_id']} - {row['name']} ({row.get('role', '')})": row['technician_id']
                        for _, row in tech_df.iterrows()}
                    technician_select = st.selectbox("责任技师", [""] + list(technician_options.keys()), index=0)

            description = st.text_area("维修描述", placeholder="详细描述维修内容和发现的问题")

            submitted = st.form_submit_button("提交维修记录")

            if submitted:
                if not available_df.empty and not component_select:
                    st.error("请选择维修部件")
                elif start_datetime > end_datetime:
                    st.error("维修结束时间不能早于开始时间")
                else:
                    try:
                        component_id = component_options[component_select]
                        responsible_id = technician_options[
                            technician_select] if technician_select and technician_select in technician_options else None

                        result = register_maintenance(
                            component_id=component_id,
                            maintenance_start=start_datetime,
                            maintenance_end=end_datetime,
                            maintenance_type=maintenance_type,
                            result=result_type,
                            description=description if description else None,
                            responsible_technician_id=responsible_id
                        )
                        st.success(
                            f"✅ {result.get('message', '维修记录登记成功')}，记录ID: {result.get('maintenance_record_id', 'N/A')}")

                    except BusinessError as e:
                        st.error(f"❌ 维修登记失败: {e}")
                    except Exception as e:
                        st.error(f"❌ 系统错误: {e}")

# ============================================================
# 页面4: 飞行日志
# ============================================================
def page_flight_log():
    st.title("📝 飞行日志")

    tab1, tab2 = st.tabs(["日志列表", "新增日志"])

    with tab1:
        st.subheader("飞行日志列表")

        log_query = """
            SELECT 
                fl.*,
                a.registration_number,
                a.model as aircraft_model
            FROM FlightLog fl
            JOIN Aircraft a ON fl.aircraft_id = a.aircraft_id
            ORDER BY fl.takeoff_time DESC
        """
        log_df = run_query(log_query)

        if not log_df.empty:
            log_df['takeoff_time'] = pd.to_datetime(log_df['takeoff_time']).dt.strftime('%Y-%m-%d %H:%M')
            log_df['landing_time'] = pd.to_datetime(log_df['landing_time']).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(log_df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无飞行日志")

    with tab2:
        st.subheader("新增飞行日志")

        # 获取在役飞机列表
        aircraft_df = run_query("""
            SELECT aircraft_id, registration_number, model, status
            FROM Aircraft
            WHERE status = 'ACTIVE'
            ORDER BY registration_number
        """)

        with st.form("add_flight"):
            col1, col2 = st.columns(2)
            with col1:
                if aircraft_df.empty:
                    st.warning("⚠️ 没有在役的飞机可供登记飞行日志")
                    aircraft_options = {}
                else:
                    aircraft_options = {
                        f"{row['aircraft_id']} - {row['registration_number']} ({row['model']})": row['aircraft_id']
                        for _, row in aircraft_df.iterrows()}
                    aircraft_select = st.selectbox("选择飞机 *", list(aircraft_options.keys()))

                mission_type = st.selectbox(
                    "任务类型",
                    ["训练", "运输", "巡逻", "救援", "巡检", "测试飞行", "其他"]
                )

            with col2:
                takeoff_time = st.datetime_input("起飞时间 *", value=datetime.now())
                landing_time = st.datetime_input("降落时间 *", value=datetime.now())

            submitted = st.form_submit_button("提交飞行日志")

            if submitted:
                if not aircraft_df.empty and not aircraft_select:
                    st.error("请选择飞机")
                elif takeoff_time >= landing_time:
                    st.error("降落时间必须晚于起飞时间")
                else:
                    try:
                        aircraft_id = aircraft_options[aircraft_select]

                        result = add_flight_log(
                            aircraft_id=aircraft_id,
                            takeoff_time=takeoff_time,
                            landing_time=landing_time,
                            mission_type=mission_type
                        )

                        flight_duration = result.get('flight_duration_minutes', '计算中')
                        st.success(f"✅ {result.get('message', '飞行日志登记成功')}，飞行时长: {flight_duration} 分钟")

                    except BusinessError as e:
                        st.error(f"❌ 飞行日志登记失败: {e}")
                    except Exception as e:
                        st.error(f"❌ 系统错误: {e}")

# ============================================================
# 页面5: 生命周期追溯
# ============================================================
def page_traceability():
    st.title("🔍 生命周期追溯")

    st.markdown("输入部件序列号查询其完整的生命周期历程")

    serial_input = st.text_input("请输入部件序列号", placeholder="例如: SN-001")

    if serial_input:
        # 查询部件信息
        component_query = """
            SELECT c.*, cm.name as model_name, cm.category
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            WHERE c.serial_number = %s
        """
        component_df = run_query(component_query, (serial_input,))

        if component_df.empty:
            st.error("未找到该序列号的部件")
            return

        comp = component_df.iloc[0]

        # 部件基本信息
        st.subheader("📋 部件信息")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("序列号", comp['serial_number'])
        col2.metric("型号", comp['model_name'])
        col3.metric("类别", comp['category'])
        col4.metric("状态", comp['current_status'])

        col1, col2, col3 = st.columns(3)
        col1.metric("总使用时长", f"{comp['total_usage_hours']:.1f}h")
        col1, col2 = st.columns(2)
        col1.metric("入库日期", pd.to_datetime(comp['entry_date']).strftime('%Y-%m-%d'))
        col2.metric("生产日期", pd.to_datetime(comp['production_date']).strftime('%Y-%m-%d'))

        st.markdown("---")

        # 生命周期时间线（表格形式）
        st.subheader("📊 生命周期时间线")
        timeline_df, error = create_lifecycle_gantt(comp['component_id'], comp['serial_number'])

        if error:
            st.warning(error)
        elif timeline_df is not None and not timeline_df.empty:
            st.dataframe(timeline_df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无生命周期记录")

        st.markdown("---")

        # 详细记录
        col_install, col_maint = st.columns(2)

        with col_install:
            st.subheader("🔧 安装记录")
            install_query = """
                SELECT ir.*, a.registration_number, a.model as aircraft_model
                FROM InstallationRecord ir
                JOIN Aircraft a ON ir.aircraft_id = a.aircraft_id
                WHERE ir.component_id = %s
                ORDER BY ir.install_time DESC
            """
            install_df = run_query(install_query, (comp['component_id'],))

            if not install_df.empty:
                install_df['install_time'] = pd.to_datetime(install_df['install_time']).dt.strftime('%Y-%m-%d %H:%M')
                install_df['remove_time'] = pd.to_datetime(install_df['remove_time']).apply(
                    lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) else '安装中'
                )
                st.dataframe(install_df[['install_time', 'remove_time', 'registration_number', 'position', 'install_reason']],
                           use_container_width=True, hide_index=True)
            else:
                st.info("无安装记录")

        with col_maint:
            st.subheader("🔩 维修记录")
            maint_query = """
                SELECT * FROM MaintenanceRecord
                WHERE component_id = %s
                ORDER BY maintenance_start DESC
            """
            maint_df = run_query(maint_query, (comp['component_id'],))

            if not maint_df.empty:
                maint_df['maintenance_start'] = pd.to_datetime(maint_df['maintenance_start']).dt.strftime('%Y-%m-%d')
                maint_df['maintenance_end'] = pd.to_datetime(maint_df['maintenance_end']).apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else '进行中'
                )
                st.dataframe(maint_df[['maintenance_start', 'maintenance_end', 'maintenance_type', 'result']],
                           use_container_width=True, hide_index=True)
            else:
                st.info("无维修记录")

# ============================================================
# 页面6: 统计分析
# ============================================================
def page_statistics():
    st.title("📊 统计分析")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "飞行时长统计", "型号可靠性分析", "维修频率分析",
        "故障集中分析", "状态流转分析", "型号可靠性评估"
    ])

    # Tab1: 飞行时长统计
    with tab1:
        st.subheader("飞行时长统计")

        flight_query = """
            SELECT 
                a.registration_number,
                a.model,
                SUM(fl.flight_duration_minutes) as total_minutes,
                COUNT(fl.flight_id) as flight_count
            FROM Aircraft a
            LEFT JOIN FlightLog fl ON a.aircraft_id = fl.aircraft_id
            GROUP BY a.aircraft_id, a.registration_number, a.model
            ORDER BY total_minutes DESC
        """
        flight_df = run_query(flight_query)

        if not flight_df.empty:
            flight_df['total_hours'] = flight_df['total_minutes'] / 60

            fig = go.Figure(data=[go.Bar(
                x=flight_df['registration_number'],
                y=flight_df['total_hours'],
                marker_color='#45B7D1',
                hovertemplate='飞机: %{x}<br>飞行时长: %{y:.1f}小时<extra></extra>'
            )])
            fig.update_layout(
                title='各飞机累计飞行时长',
                xaxis_title='飞机注册号',
                yaxis_title='飞行时长(小时)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(flight_df[['registration_number', 'model', 'flight_count', 'total_hours']],
                        use_container_width=True, hide_index=True)

    # Tab2: 型号可靠性分析
    with tab2:
        st.subheader("型号可靠性分析")

        reliability_query = """
            SELECT 
                cm.name,
                COUNT(DISTINCT c.component_id) as total_count,
                SUM(CASE WHEN c.current_status = 'RETIRED' THEN 1 ELSE 0 END) as retired_count,
                COUNT(mr.record_id) as maintenance_count,
                AVG(c.total_usage_hours) as avg_usage_hours
            FROM ComponentModel cm
            LEFT JOIN Component c ON cm.model_id = c.model_id
            LEFT JOIN MaintenanceRecord mr ON c.component_id = mr.component_id
            GROUP BY cm.model_id, cm.name
        """
        reliability_df = run_query(reliability_query)

        if not reliability_df.empty:
            # 修复：避免除以0的错误
            reliability_df['retired_rate'] = reliability_df.apply(
                lambda row: row['retired_count'] / row['total_count'] if row['total_count'] > 0 else 0,
                axis=1
            )

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=reliability_df['name'],
                y=reliability_df['total_count'],
                name='在用数量',
                marker_color='#4ECDC4'
            ))
            fig.add_trace(go.Bar(
                x=reliability_df['name'],
                y=reliability_df['retired_count'],
                name='退役数量',
                marker_color='#D64933'
            ))
            fig.update_layout(
                title='各型号部件数量统计',
                xaxis_title='型号',
                yaxis_title='数量',
                barmode='group',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

    # Tab3: 维修频率分析
    with tab3:
        st.subheader("维修频率分析")

        freq_query = """
            SELECT 
                cm.name,
                DATE_FORMAT(mr.maintenance_start, '%Y-%m') as month,
                COUNT(*) as count
            FROM MaintenanceRecord mr
            JOIN Component c ON mr.component_id = c.component_id
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            GROUP BY cm.name, DATE_FORMAT(mr.maintenance_start, '%Y-%m')
            ORDER BY month
        """
        freq_df = run_query(freq_query)

        if not freq_df.empty:
            pivot = freq_df.pivot(index='month', columns='name', values='count').fillna(0)

            fig = go.Figure()
            for col in pivot.columns:
                fig.add_trace(go.Scatter(
                    x=pivot.index,
                    y=pivot[col],
                    mode='lines+markers',
                    name=col
                ))
            fig.update_layout(
                title='各型号月度维修频率',
                xaxis_title='月份',
                yaxis_title='维修次数',
                height=400,
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

    # Tab4: 故障集中分析 (新增)
    with tab4:
        st.subheader("故障集中分析")

        table_df, pie_fig, error = create_fault_analysis()

        if error:
            st.warning(error)
        else:
            col1, col2 = st.columns([2, 1])

            with col1:
                st.dataframe(
                    table_df,
                    use_container_width=True,
                    hide_index=True,
                    height=450
                )

            with col2:
                st.plotly_chart(
                    pie_fig,
                    use_container_width=True
                )

    # Tab5: 状态流转分析 (新增)
    with tab5:
        st.subheader("部件状态流转分析")

        sankey_fig, pie_fig = create_sankey_diagram()

        col1, col2 = st.columns(2)
        with col1:
            if sankey_fig:
                st.plotly_chart(sankey_fig, use_container_width=True)
        with col2:
            if pie_fig:
                st.plotly_chart(pie_fig, use_container_width=True)

    # Tab6: 型号可靠性评估 (新增)
    with tab6:
        st.subheader("型号可靠性评估")

        # 获取所有型号
        models_query = "SELECT DISTINCT name FROM ComponentModel"
        models_df = run_query(models_query)
        all_models = models_df['name'].tolist() if not models_df.empty else []

        selected = st.multiselect("选择要比较的型号", all_models, default=all_models[:3] if len(all_models) >= 3 else all_models)

        radar_fig, error = create_reliability_radar(selected)

        if error:
            st.warning(error)
        else:
            if radar_fig:
                st.plotly_chart(
                    radar_fig,
                    use_container_width=True
                )


# ============================================================
# 页面7: 异常检测
# ============================================================
def page_anomaly():
    st.title("⚠️ 异常检测")

    # 检测规则定义
    anomaly_tabs = st.tabs(["超期未维修", "使用时长异常", "状态异常", "维修周期异常", "退役风险"])

    with anomaly_tabs[0]:
        st.subheader("超期未维修部件")

        overdue_query = """
            SELECT c.*, cm.name as model_name, cm.maintenance_interval_hours
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            WHERE c.total_usage_hours > cm.maintenance_interval_hours
            AND c.current_status = 'INSTALLED'
            AND NOT EXISTS (
                SELECT 1 FROM MaintenanceRecord mr 
                WHERE mr.component_id = c.component_id 
                AND mr.maintenance_end IS NOT NULL
            )
        """
        overdue_df = run_query(overdue_query)

        if not overdue_df.empty:
            st.error(f"发现 {len(overdue_df)} 个部件超期未维修")
            st.dataframe(overdue_df[['serial_number', 'model_name', 'total_usage_hours', 'maintenance_interval_hours']],
                        use_container_width=True, hide_index=True)
        else:
            st.success("暂无超期未维修部件")

    with anomaly_tabs[1]:
        st.subheader("使用时长异常部件")

        # 查找使用时长超过设计寿命的部件
        lifespan_query = """
            SELECT c.*, cm.name as model_name, cm.design_life_hours
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            WHERE c.total_usage_hours > cm.design_life_hours * 0.9
        """
        lifespan_df = run_query(lifespan_query)

        if not lifespan_df.empty:
            st.warning(f"发现 {len(lifespan_df)} 个部件接近或超过设计寿命")
            st.dataframe(lifespan_df[['serial_number', 'model_name', 'total_usage_hours', 'design_life_hours']],
                        use_container_width=True, hide_index=True)
        else:
            st.success("暂无使用时长异常部件")

    with anomaly_tabs[2]:
        st.subheader("状态异常部件")

        # 状态与记录不匹配
        mismatch_query = """
            SELECT c.*, cm.name as model_name
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = cm.model_id
            WHERE c.current_status = 'INSTALLED'
            AND NOT EXISTS (
                SELECT 1 FROM InstallationRecord ir 
                WHERE ir.component_id = c.component_id 
                AND ir.remove_time IS NULL
            )
        """
        mismatch_df = run_query(mismatch_query)

        if not mismatch_df.empty:
            st.error(f"发现 {len(mismatch_df)} 个部件状态与安装记录不匹配")
            st.dataframe(mismatch_df[['serial_number', 'model_name', 'current_status']],
                        use_container_width=True, hide_index=True)
        else:
            st.success("暂无状态异常部件")

    with anomaly_tabs[3]:
        st.subheader("维修周期异常")

        # 同一部件频繁维修
        frequent_query = """
            SELECT component_id, COUNT(*) as repair_count
            FROM MaintenanceRecord
            WHERE maintenance_start >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
            GROUP BY component_id
            HAVING repair_count > 3
        """
        frequent_df = run_query(frequent_query)

        if not frequent_df.empty:
            st.warning(f"发现 {len(frequent_df)} 个部件维修过于频繁")
            st.dataframe(frequent_df, use_container_width=True, hide_index=True)
        else:
            st.success("暂无维修周期异常部件")

    with anomaly_tabs[4]:
        st.subheader("退役风险部件")

        # 高使用时长但未退役
        risk_query = """
            SELECT c.*, cm.name as model_name, cm.design_life_hours
            FROM Component c
            JOIN ComponentModel cm ON c.model_id = c.model_id
            WHERE c.total_usage_hours > cm.design_life_hours * 0.95
            AND c.current_status != 'RETIRED'
        """
        risk_df = run_query(risk_query)

        if not risk_df.empty:
            st.error(f"发现 {len(risk_df)} 个高风险部件")
            st.dataframe(risk_df[['serial_number', 'model_name', 'total_usage_hours', 'design_life_hours']],
                        use_container_width=True, hide_index=True)
        else:
            st.success("暂无退役风险部件")


# ============================================================
# 主程序入口
# ============================================================
if __name__ == "__main__":
    if page == "🏠 首页":
        page_home()
    elif page == "📦 部件管理":
        page_component()
    elif page == "🔧 维修管理":
        page_maintenance()
    elif page == "📝 飞行日志":
        page_flight_log()
    elif page == "🔍 生命周期追溯":
        page_traceability()
    elif page == "📊 统计分析":
        page_statistics()
    elif page == "⚠️ 异常检测":
        page_anomaly()

