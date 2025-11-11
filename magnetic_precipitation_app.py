import streamlit as st
import math
import pandas as pd


class MagneticPrecipitationCalculator:
    def __init__(self):
        # 固定参数
        self.dynamic_viscosity = 0.00114  # Pa.s
        self.gravity = 9.81  # m/s²
        self.resistance_coefficient = 0.5
        self.paddle_blades = 2
        self.paddle_angle = 45  # 度
        self.motor_condition_factor = 1.2
        self.reducer_efficiency = 0.95
        self.bearing_efficiency = 0.99

        # 电机功率选型列表
        self.motor_power_options = [0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3, 4, 5.5, 7.5, 11, 15, 22]

    def check_water_quality_feasibility(self, tp_in, tp_out, ss_in, ss_out):
        """第一步：判断水质处理效果是否能实现"""
        # 工况1：水质提标一般水质
        condition1 = (tp_in <= 3 and tp_out <= 0.3 and
                      ss_in <= 100 and ss_out <= 10)

        # 工况2：污染物削减一般水质
        condition2 = (tp_in <= 8 and tp_out < 0.5 and
                      ss_in <= 500 and ss_out <= 30)

        return condition1 or condition2

    def check_water_quality_warnings(self, ph, temperature, extra_ss, chloride,
                                     sulfate, calcium_magnesium, dom, heavy_metals):
        """第二步：检查水质参数警告"""
        warnings = []

        if ph < 6.5 or ph > 8.0:
            warnings.append(f"pH值异常: {ph} (正常范围: 6.5-8.0)")

        if temperature < 10 or temperature > 35:
            warnings.append(f"水温异常: {temperature}°C (正常范围: 10-35°C)")

        if extra_ss > 0:
            warnings.append(f"工艺额外产生SS类物质: {extra_ss} mg/L")

        if chloride > 0:
            warnings.append(f"氯离子浓度: {chloride} mg/L")

        if sulfate > 0:
            warnings.append(f"硫酸根离子浓度: {sulfate} mg/L")

        if calcium_magnesium > 0:
            warnings.append(f"钙镁离子浓度: {calcium_magnesium} mg/L")

        if dom > 0:
            warnings.append(f"溶解性有机物(DOM): {dom} mg/L")

        if heavy_metals > 0:
            warnings.append(f"重金属离子浓度: {heavy_metals} mg/L")

        return warnings

    def calculate_flow_rate(self, total_flow, num_units, variation_coefficient):
        """第三步：计算水量"""
        q0 = total_flow / num_units  # 单套设备处理量
        q_max = q0 * variation_coefficient  # 单套设备最大处理量
        return q0, q_max

    def select_motor_power(self, calculated_power):
        """电机功率选型"""
        if calculated_power < 2.5:
            required_power = calculated_power * 1.2
        else:
            required_power = calculated_power + 0.5

        # 向上取整到最近的电机功率选项
        for power in self.motor_power_options:
            if power >= required_power:
                return power
        return self.motor_power_options[-1]  # 如果超过最大值，返回最大功率

    def calculate_t1_parameters(self, ss_in, flow_rate, construction_type, pool_shape, d1=None, v1=None):
        """T1反应池参数计算"""
        results = {}

        # 水的密度
        water_density = 1050  # kg/m³

        # ① 确定停留时间 t1
        if ss_in >= 150:
            t1 = 90
        elif ss_in > 100:
            t1 = 80
        elif ss_in > 20:
            t1 = 70
        else:
            t1 = 60
        results['t1'] = t1

        # ② 计算反应池体积 V1
        V1 = (flow_rate * t1) / (24 * 3600)
        results['V1'] = V1

        # ③ 反应池尺寸确认
        if pool_shape == "圆形":
            # 圆形池体
            D = (V1 / 1.5) ** (1 / 3)  # h2/D = 1.5
            h2 = 1.5 * D
            l = None
            w = None
        else:
            # 矩形池体
            l = (V1 / 1.5) ** (1 / 3)  # l=w, h2/D=1.5
            w = l
            D = math.sqrt((4 * l * w) / math.pi)
            h2 = 1.5 * D
        results['D'] = D
        results['l'] = l
        results['w'] = w
        results['h2'] = h2

        # 调用通用计算函数完成剩余计算
        self._calculate_common_parameters(results, ss_in, flow_rate, construction_type, pool_shape,
                                          water_density, d1, v1, "T1")

        return results

    def calculate_t2_parameters(self, ss_in, flow_rate, construction_type, pool_shape, d1=None, v1=None):
        """T2反应池参数计算"""
        results = {}

        # 水的密度
        water_density = 1150  # kg/m³

        # ① 确定停留时间 t1
        if ss_in >= 130:
            t1 = 120
        elif ss_in > 100:
            t1 = 110
        elif ss_in > 20:
            t1 = 100
        else:
            t1 = 90
        results['t1'] = t1

        # ② 计算反应池体积 V1
        V1 = (flow_rate * t1) / (24 * 3600)
        results['V1'] = V1

        # ③ 反应池尺寸确认
        if pool_shape == "圆形":
            # 圆形池体
            D = (V1 / 1.5) ** (1 / 3)  # h2/D = 1.5
            h2 = 1.5 * D
            l = None
            w = None
        else:
            # 矩形池体
            l = (V1 / 1.5) ** (1 / 3)  # l=w, h2/D=1.5
            w = l
            D = math.sqrt((4 * l * w) / math.pi)
            h2 = 1.5 * D
        results['D'] = D
        results['l'] = l
        results['w'] = w
        results['h2'] = h2

        # 调用通用计算函数完成剩余计算
        self._calculate_common_parameters(results, ss_in, flow_rate, construction_type, pool_shape,
                                          water_density, d1, v1, "T2")

        return results

    def _calculate_common_parameters(self, results, ss_in, flow_rate, construction_type, pool_shape,
                                     water_density, d1=None, v1=None, reactor_type="T1"):
        """通用参数计算（T1和T2反应池共用）"""
        # 池体超高 h1
        h1 = 0.3 if construction_type == "钢结构" else 0.5
        results['h1'] = h1
        results['h_total'] = h1 + results['h2']

        # 搅拌桨叶外缘线速度 v1
        if v1 is None:
            if reactor_type == "T1":
                # T1反应池的v1取值
                if 50 <= ss_in < 250:
                    v1 = 4.3
                elif 250 <= ss_in < 400:
                    v1 = 4.4
                elif 400 <= ss_in <= 500:
                    v1 = 4.5
                else:
                    v1 = 4.2  # 默认值
            else:
                # T2反应池的v1取值（更新后的规则）
                if ss_in <= 250:
                    v1 = 3.5
                elif ss_in <= 400:
                    v1 = 3.8
                else:
                    v1 = 4.1
        results['v1'] = v1

        # 搅拌直径 d1
        if d1 is None:
            # 如果用户没有提供d1，则根据SS值自动确定
            if ss_in >= 500:
                d1_ratio = 0.5
            elif ss_in > 100:
                # 线性相关
                d1_ratio = 1 / 3 + (ss_in - 100) * (1 / 2 - 1 / 3) / 400
            else:
                d1_ratio = 1 / 3

            d1 = d1_ratio * results['D']
            # 向上取整到10mm
            d1 = math.ceil(d1 * 100) / 100

        results['d1'] = d1

        # 复核 S1/S 范围（改回小于0.2）
        if pool_shape == "圆形":
            S = (math.pi * results['D'] ** 2) / 4
        else:
            S = results['l'] * results['w'] if results['l'] and results['w'] else 0

        S1 = (math.pi * d1 ** 2) / 4
        s1_s_ratio = S1 / S
        results['S1_S_ratio'] = s1_s_ratio
        results['S1_S_in_range'] = s1_s_ratio < 0.25

        # 搅拌器桨叶宽度 b (更新后的规则)
        if d1 <= 0.5:
            b = 0.10
        elif d1 < 1:
            b = 0.15
        elif d1 < 1.6:
            b = 0.20
        elif d1 < 2:
            b = 0.25
        else:
            b = 0.30
        results['b'] = b

        # ⑥ 搅拌功率 N1
        # 转速 n1
        n1 = (60 * v1) / (math.pi * d1)
        results['n1'] = n1

        # 角速度 w1
        w1 = (2 * v1) / d1
        results['w1'] = w1

        # 搅拌层数 e
        h2_D_ratio = results['h2'] / results['D']
        e = 2 if h2_D_ratio > 1.3 else 1
        results['e'] = e

        # 搅拌器半径 R1
        R1 = 0.5 * d1

        # 搅拌功率 N1
        N1 = (self.resistance_coefficient * water_density * (w1 ** 3) *
              self.paddle_blades * e * b * (R1 ** 4) * math.sin(math.radians(self.paddle_angle))) / (408 * self.gravity)
        results['N1'] = N1

        # ⑦ 电动机功率 Na1
        Na1 = (self.motor_condition_factor * N1) / (self.reducer_efficiency * self.bearing_efficiency)
        results['Na1'] = Na1

        # 电动机选型功率
        selected_motor_power = self.select_motor_power(Na1)
        results['selected_motor_power'] = selected_motor_power

        # ⑧ 速度梯度 G1 复核
        Q_max1 = flow_rate / (24 * 3600)  # m³/s
        G1 = math.sqrt((1000 * N1) / (self.dynamic_viscosity * Q_max1 * results['t1']))
        results['G1'] = G1

        # 根据反应池类型设置G1的正常范围
        if reactor_type == "T1":
            results['G1_in_range'] = 250 <= G1 <= 400
            results['G1_range'] = (250, 400)
        else:
            results['G1_in_range'] = 200 <= G1 <= 300
            results['G1_range'] = (200, 300)


def main():
    st.set_page_config(page_title="磁沉淀工艺计算系统", layout="wide")
    st.title("🧲 磁沉淀工艺计算系统")

    calculator = MagneticPrecipitationCalculator()

    # 使用会话状态存储计算结果
    if 't1_results' not in st.session_state:
        st.session_state.t1_results = None
    if 'show_adjustment' not in st.session_state:
        st.session_state.show_adjustment = False
    if 'calculation_completed' not in st.session_state:
        st.session_state.calculation_completed = False

    # 侧边栏输入参数
    st.sidebar.header("📋 输入参数")

    # 反应池类型选择
    reactor_type = st.sidebar.selectbox(
        "反应池类型",
        ["T1反应池", "T2反应池"],
        help="选择要计算的反应池类型"
    )

    # 计算模式选择
    calculation_mode = st.sidebar.selectbox(
        "计算模式",
        ["正向计算", "反向计算"],
        help="正向计算：根据水质参数计算池体尺寸\n反向计算：根据池体尺寸验证水力停留时间"
    )

    # 流量选择
    flow_selection = st.sidebar.selectbox(
        "流量选择",
        ["使用单套设备最大处理量 Qmax", "使用单套设备需求处理量 Q0"],
        help="选择计算中使用的流量参数"
    )

    # 基本参数
    st.sidebar.subheader("基本参数")
    total_flow = st.sidebar.number_input("总处理水量 Q总 (m³/d)", min_value=1.0, value=1000.0)
    num_units = st.sidebar.number_input("设备需求套数 n", min_value=1, value=2)
    variation_coefficient = st.sidebar.number_input("变化系数 Kz", min_value=1.0, value=1.2)

    # 水质参数
    st.sidebar.subheader("水质参数")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        tp_in = st.number_input("进水TP值 (mg/L)", min_value=0.0, value=2.0)
        ss_in = st.number_input("进水SS值 (mg/L)", min_value=0.0, value=80.0)
    with col2:
        tp_out = st.number_input("出水TP值 (mg/L)", min_value=0.0, value=0.2)
        ss_out = st.number_input("出水SS值 (mg/L)", min_value=0.0, value=8.0)

    # 其他参数
    st.sidebar.subheader("其他参数")
    construction_type = st.sidebar.selectbox("建设形式", ["钢结构", "土建"])
    pool_shape = st.sidebar.selectbox("反应池池体形状", ["圆形", "矩形"])

    # 初始化变量，避免未绑定错误
    l, w, h2 = None, None, None

    # 反向计算专用输入
    if calculation_mode == "反向计算":
        st.sidebar.subheader("池体尺寸参数（反向计算）")
        if pool_shape == "圆形":
            D_input = st.sidebar.number_input("池体直径 D (m)", min_value=0.1, value=2.0)
            h2 = st.sidebar.number_input("有效高度 h2 (m)", min_value=0.1, value=3.0)
            l = D_input  # 圆形池体使用l存储直径
            w = None
        else:
            l = st.sidebar.number_input("池体长度 l (m)", min_value=0.1, value=2.0)
            w = st.sidebar.number_input("池体宽度 w (m)", min_value=0.1, value=2.0)
            h2 = st.sidebar.number_input("有效高度 h2 (m)", min_value=0.1, value=3.0)

    # 水质影响参数
    st.sidebar.subheader("水质影响参数")
    ph = st.sidebar.number_input("pH值", min_value=0.0, max_value=14.0, value=7.0)
    temperature = st.sidebar.number_input("水温 (°C)", min_value=0.0, value=20.0)
    extra_ss = st.sidebar.number_input("工艺额外产生的SS类物质 (mg/L)", min_value=0.0, value=0.0)
    chloride = st.sidebar.number_input("氯离子 (mg/L)", min_value=0.0, value=0.0)
    sulfate = st.sidebar.number_input("硫酸根离子 (mg/L)", min_value=0.0, value=0.0)
    calcium_magnesium = st.sidebar.number_input("钙镁离子 (mg/L)", min_value=0.0, value=0.0)
    dom = st.sidebar.number_input("溶解性有机物(DOM) (mg/L)", min_value=0.0, value=0.0)
    heavy_metals = st.sidebar.number_input("重金属离子 (mg/L)", min_value=0.0, value=0.0)

    # 计算按钮
    if st.sidebar.button("开始计算", type="primary"):
        # 第一步：判断水质处理效果
        st.header("第一步：水质处理效果判断")
        feasible = calculator.check_water_quality_feasibility(tp_in, tp_out, ss_in, ss_out)

        if not feasible:
            st.error("❌ 需人工经验复核内容较多，转人工设计")
            st.stop()
        else:
            st.success("✅ 水质处理效果在可行范围内，继续计算")

        # 第二步：水质参数警告
        st.header("第二步：水质参数检查")
        warnings = calculator.check_water_quality_warnings(
            ph, temperature, extra_ss, chloride, sulfate,
            calcium_magnesium, dom, heavy_metals
        )

        if warnings:
            st.warning("⚠️ 水质参数警告：")
            for warning in warnings:
                st.write(f"- {warning}")
        else:
            st.success("✅ 所有水质参数均在正常范围内")

        # 第三步：计算水量
        st.header("第三步：水量计算")
        q0, q_max = calculator.calculate_flow_rate(total_flow, num_units, variation_coefficient)

        # 根据用户选择确定使用的流量
        if flow_selection == "使用单套设备最大处理量 Qmax":
            flow_rate = q_max
            flow_display_name = "Qmax"
        else:
            flow_rate = q0
            flow_display_name = "Q0"

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总处理水量", f"{total_flow:.2f} m³/d")
        with col2:
            st.metric("单套设备处理量 Q0", f"{q0:.2f} m³/d")
        with col3:
            st.metric("单套设备最大处理量 Qmax", f"{q_max:.2f} m³/d")
        with col4:
            st.metric(f"计算使用的流量 ({flow_display_name})", f"{flow_rate:.2f} m³/d")

        # 第四步：计算反应池参数
        st.header(f"第四步：{reactor_type}参数计算")

        if calculation_mode == "正向计算":
            st.info(f"🔍 正向计算模式：根据水质参数计算{reactor_type}池体尺寸")
            if reactor_type == "T1反应池":
                t1_results = calculator.calculate_t1_parameters(
                    ss_in, flow_rate, construction_type, pool_shape
                )
            else:
                t1_results = calculator.calculate_t2_parameters(
                    ss_in, flow_rate, construction_type, pool_shape
                )
        else:
            st.info(f"🔍 反向计算模式：根据池体尺寸验证{reactor_type}水力停留时间")
            # 确保l和h2有值
            if l is None or h2 is None:
                st.error("❌ 反向计算需要输入池体尺寸参数")
                st.stop()

            if reactor_type == "T1反应池":
                t1_results = calculator.calculate_t1_parameters(
                    ss_in, flow_rate, construction_type, pool_shape, l, w, h2
                )
            else:
                t1_results = calculator.calculate_t2_parameters(
                    ss_in, flow_rate, construction_type, pool_shape, l, w, h2
                )

        # 保存计算结果到会话状态
        st.session_state.t1_results = t1_results
        st.session_state.calculation_completed = True
        st.session_state.flow_selection = flow_selection  # 保存流量选择
        st.session_state.calculation_mode = calculation_mode  # 保存计算模式
        st.session_state.pool_shape = pool_shape  # 保存池体形状
        st.session_state.q0 = q0  # 保存Q0
        st.session_state.q_max = q_max  # 保存Qmax
        st.session_state.flow_rate = flow_rate  # 保存使用的流量
        st.session_state.flow_display_name = flow_display_name  # 保存流量显示名称
        st.session_state.l = l  # 保存l值
        st.session_state.w = w  # 保存w值
        st.session_state.reactor_type = reactor_type  # 保存反应池类型

        # 检查G1是否在范围内
        g1_min, g1_max = t1_results['G1_range']
        if not t1_results['G1_in_range']:
            st.session_state.show_adjustment = True
            st.error(f"❌ 速度梯度 G1 不在正常范围内: {t1_results['G1']:.2f} s⁻¹ (正常范围: {g1_min}-{g1_max} s⁻¹)")
            st.info("💡 您可以手动调整搅拌参数来优化速度梯度")
        else:
            st.session_state.show_adjustment = False
            st.success(f"✅ 速度梯度 G1 在正常范围内 ({g1_min}-{g1_max} s⁻¹)")

        # 显示计算结果
        display_results()

    # 如果计算结果已存在且需要调整，显示调整界面
    if st.session_state.calculation_completed and st.session_state.show_adjustment:
        st.header("🔄 搅拌参数调整")
        g1_min, g1_max = st.session_state.t1_results['G1_range']
        st.info(f"请调整以下参数以使速度梯度 G1 进入正常范围 ({g1_min}-{g1_max} s⁻¹)")

        col1, col2 = st.columns(2)
        with col1:
            # 获取当前值作为默认值
            current_d1 = st.session_state.t1_results['d1']
            adjusted_d1 = st.number_input("搅拌直径 d1 (m)", min_value=0.1, max_value=10.0, value=current_d1, step=0.1)

        with col2:
            current_v1 = st.session_state.t1_results['v1']
            adjusted_v1 = st.number_input("搅拌桨叶外缘线速度 v1 (m/s)", min_value=1.0, max_value=10.0,
                                          value=current_v1, step=0.1)

        if st.button("重新计算", type="primary"):
            # 使用调整后的参数重新计算
            if st.session_state.reactor_type == "T1反应池":
                if st.session_state.calculation_mode == "正向计算":
                    adjusted_results = calculator.calculate_t1_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape, adjusted_d1,
                        adjusted_v1
                    )
                else:
                    adjusted_results = calculator.calculate_t1_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape,
                        st.session_state.l, st.session_state.w, st.session_state.t1_results['h2'], adjusted_d1,
                        adjusted_v1
                    )
            else:
                if st.session_state.calculation_mode == "正向计算":
                    adjusted_results = calculator.calculate_t2_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape, adjusted_d1,
                        adjusted_v1
                    )
                else:
                    adjusted_results = calculator.calculate_t2_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape,
                        st.session_state.l, st.session_state.w, st.session_state.t1_results['h2'], adjusted_d1,
                        adjusted_v1
                    )

            # 更新会话状态
            st.session_state.t1_results = adjusted_results

            # 检查调整后的G1
            g1_min, g1_max = adjusted_results['G1_range']
            if adjusted_results['G1_in_range']:
                st.session_state.show_adjustment = False
                st.success(f"✅ 调整成功！速度梯度 G1 现在在正常范围内: {adjusted_results['G1']:.2f} s⁻¹")
            else:
                st.error(f"❌ 速度梯度 G1 仍然不在正常范围内: {adjusted_results['G1']:.2f} s⁻¹")

            # 显示调整后的结果
            display_results()


def display_results():
    """显示计算结果的通用函数"""
    t1_results = st.session_state.t1_results
    calculation_mode = st.session_state.calculation_mode
    pool_shape = st.session_state.pool_shape
    q0 = st.session_state.q0
    q_max = st.session_state.q_max
    flow_rate = st.session_state.flow_rate
    flow_display_name = st.session_state.flow_display_name
    flow_selection = st.session_state.flow_selection
    l = st.session_state.l
    w = st.session_state.w
    reactor_type = st.session_state.reactor_type

    # 显示主要结果
    st.subheader(f"{reactor_type}主要计算结果")

    # 分列显示结果
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**基本参数**")
        st.metric("水力停留时间 t1", f"{t1_results['t1']:.2f} s")
        st.metric("反应池体积 V1", f"{t1_results['V1']:.3f} m³")
        st.metric("池体当量直径 D", f"{t1_results['D']:.3f} m")
        if pool_shape == "矩形" and t1_results['l']:
            st.metric("池体长度 l", f"{t1_results['l']:.3f} m")
            st.metric("池体宽度 w", f"{t1_results['w']:.3f} m")
        elif calculation_mode == "反向计算" and pool_shape == "矩形":
            st.metric("池体长度 l", f"{l:.3f} m")
            st.metric("池体宽度 w", f"{w:.3f} m")

    with col2:
        st.write("**尺寸参数**")
        st.metric("有效高度 h2", f"{t1_results['h2']:.3f} m")
        st.metric("池体超高 h1", f"{t1_results['h1']:.3f} m")
        st.metric("池体总高 h总", f"{t1_results['h_total']:.3f} m")
        st.metric("搅拌直径 d1", f"{t1_results['d1']:.3f} m")

    with col3:
        st.write("**搅拌参数**")
        st.metric("桨叶线速度 v1", f"{t1_results['v1']:.2f} m/s")
        st.metric("搅拌转速 n1", f"{t1_results['n1']:.2f} r/min")
        st.metric("搅拌功率 N1", f"{t1_results['N1']:.4f} kW")
        st.metric("电动机功率 Na1", f"{t1_results['Na1']:.4f} kW")
        st.metric("电动机选型功率", f"{t1_results['selected_motor_power']} kW")

    # 显示详细结果
    st.subheader("详细计算结果")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**搅拌系统参数**")
        st.write(f"搅拌旋转角速度 w1: {t1_results['w1']:.4f} rad/s")
        st.write(f"搅拌器桨叶宽度 b: {t1_results['b']:.3f} m")
        st.write(f"搅拌层数 e: {t1_results['e']}")
        st.write(f"速度梯度 G1: {t1_results['G1']:.2f} s⁻¹")

        # 速度梯度检查
        g1_min, g1_max = t1_results['G1_range']
        if t1_results['G1_in_range']:
            st.success(f"✅ 速度梯度 G1 在正常范围内 ({g1_min}-{g1_max} s⁻¹)")
        else:
            st.error(f"❌ 速度梯度 G1 不在正常范围内: {t1_results['G1']:.2f} s⁻¹")

    with col2:
        st.write("**复核参数**")
        st.write(f"S1/S 比值: {t1_results['S1_S_ratio']:.4f}")
        if t1_results['S1_S_in_range']:
            st.success("✅ S1/S 比值满足要求 (< 0.25)")
        else:
            st.error(f"❌ S1/S 比值不小于 0.25: {t1_results['S1_S_ratio']:.4f}")

        st.write(f"h2/D 比值: {t1_results['h2'] / t1_results['D']:.3f}")

        # 反向计算特别提示
        if calculation_mode == "反向计算":
            st.info(f"📐 反向计算：根据输入的池体尺寸，反推得到水力停留时间 t1 = {t1_results['t1']:.2f} s")

    # 结果汇总表格
    st.subheader("结果汇总")
    summary_data = {
        '参数': [
            '反应池类型', '计算模式', '流量选择',
            '单套设备处理量 Q0 (m³/d)', '单套设备最大处理量 Qmax (m³/d)', '计算使用流量 (m³/d)',
            '水力停留时间 t1 (s)', '反应池体积 V1 (m³)', '池体当量直径 D (m)',
            '池体长度 l (m)', '池体宽度 w (m)', '有效高度 h2 (m)', '池体超高 h1 (m)',
            '池体总高 h总 (m)', '搅拌桨叶线速度 v1 (m/s)', '搅拌转速 n1 (r/min)',
            '搅拌直径 d1 (m)', '搅拌角速度 w1 (rad/s)', '搅拌功率 N1 (kW)',
            '搅拌器桨叶宽度 b (m)', '电动机功率 Na1 (kW)', '电动机选型功率 (kW)', '速度梯度 G1 (s⁻¹)'
        ],
        '数值': [
            reactor_type, calculation_mode, flow_selection,
            f"{q0:.2f}", f"{q_max:.2f}", f"{flow_rate:.2f}",
            f"{t1_results['t1']:.2f}", f"{t1_results['V1']:.3f}", f"{t1_results['D']:.3f}",
            f"{t1_results['l']:.3f}" if t1_results['l'] else ("N/A" if pool_shape == "圆形" else f"{l:.3f}"),
            f"{t1_results['w']:.3f}" if t1_results['w'] else ("N/A" if pool_shape == "圆形" else f"{w:.3f}"),
            f"{t1_results['h2']:.3f}", f"{t1_results['h1']:.3f}",
            f"{t1_results['h_total']:.3f}", f"{t1_results['v1']:.2f}",
            f"{t1_results['n1']:.2f}", f"{t1_results['d1']:.3f}",
            f"{t1_results['w1']:.4f}", f"{t1_results['N1']:.4f}",
            f"{t1_results['b']:.3f}", f"{t1_results['Na1']:.4f}",
            f"{t1_results['selected_motor_power']}", f"{t1_results['G1']:.2f}"
        ]
    }

    df = pd.DataFrame(summary_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()