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
        self.tube_utilization_rules = {
            3000: 0.82,
            7500: 0.87,
            15000: 0.87,
            30000: 0.91,
            999999999: 0.93  # 大于30000
        }

        self.sludge_hopper_diameter_rules = {
            2000: 0.34,
            15000: 0.42,
            30000: 0.45,
            999999999: 0.55  # 大于30000
        }

        self.sludge_hopper_height_rules = {
            2000: 0.30,
            5000: 0.40,
            15000: 0.45,
            999999999: 0.50  # 大于20000
        }

        self.collection_tank_width_rules = {
            3000: 0.20,
            7500: 0.30,
            20000: 0.35,
            999999999: 0.40  # 大于20000
        }

        self.triangle_weir_width_rules = {
            5000: 0.20,
            999999999: 0.30  # 大于5000
        }

        # 斜管长度与高度对应关系
        self.tube_length_height_map = {
            0.8: 0.693,
            1.0: 0.866,
            1.2: 1.039,
            1.5: 1.299
        }
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

    def calculate_sedimentation_pool(self, flow_rate, construction_type, total_height=None,
                                     pool_length=None, pool_width=None, tube_utilization=None,
                                     calculation_mode="正向计算", q_pac=50, q_pam=2,
                                     ss_in=80, ss_out=8, sludge_recycle_ratio=1.53,
                                     magnetic_powder_ratio=5,q_max=None):
        """沉淀池参数计算"""
        results = {}
        adjustment_log = []

        Q_h = flow_rate / 24  # 小时流量，m³/h
        if q_max is not None:
            Q_max1 = q_max / (24 * 3600)  # 最大秒流量，m³/s（使用 q_max）
        else:
            Q_max1 = flow_rate / (24 * 3600)  # 后备方案

        if calculation_mode == "正向计算":
            # 1. 确定斜管利用率
            for flow_limit, utilization in self.tube_utilization_rules.items():
                if flow_rate <= flow_limit:
                    n_tube = utilization
                    break
            results['n_tube_design'] = n_tube

            # 2. 计算沉淀池面积
            q_sedimentation = 20  # 表面水力负荷，m³/(m²·h)
            A_sedimentation = Q_h / (n_tube * q_sedimentation)

            # 3. 确定池体尺寸（正方形）
            L_pool = math.sqrt(A_sedimentation)
            B_pool = L_pool
            results['L_pool'] = L_pool
            results['B_pool'] = B_pool
            results['A_sedimentation'] = A_sedimentation

            # 4. 确定斜管长度
            if total_height is None:
                # 根据总高选择斜管长度
                if total_height < 2.9:
                    l_tube = 0.8
                elif total_height < 4.8:
                    l_tube = 1.0
                elif total_height < 6:
                    l_tube = 1.2
                else:
                    l_tube = 1.5
            else:
                # 根据处理量估算总高，选择斜管长度
                estimated_height = 2 + flow_rate / 5000  # 简单估算
                if estimated_height < 2.9:
                    l_tube = 0.8
                elif estimated_height < 4.8:
                    l_tube = 1.0
                elif estimated_height < 6:
                    l_tube = 1.2
                else:
                    l_tube = 1.5

            # 遮挡距离
            l_occlusion_map = {0.8: 0.4, 1.0: 0.5, 1.2: 0.6, 1.5: 0.75}
            l_occlusion = l_occlusion_map[l_tube]

            # 实际斜管利用率
            n_tube_actual = (L_pool - l_occlusion) / L_pool
            results['n_tube_actual'] = n_tube_actual
            results['l_tube'] = l_tube
            results['l_occlusion'] = l_occlusion
            results['h3_sedimentation'] = self.tube_length_height_map[l_tube]

        else:
            # 反向计算模式
            L_pool = pool_length
            B_pool = pool_width
            results['L_pool'] = L_pool
            results['B_pool'] = B_pool
            results['A_sedimentation'] = L_pool * B_pool

            # 计算实际斜管利用率
            n_tube_actual = tube_utilization
            results['n_tube_actual'] = n_tube_actual

            # 计算表面负荷
            q_sedimentation = Q_h / (n_tube_actual * L_pool * B_pool)
            results['q_sedimentation'] = q_sedimentation

        # 5. 布水区计算
        v_water_distribution = 0.08  # m/s
        b_water_distribution = Q_max1 / (v_water_distribution * B_pool)

        if b_water_distribution < 0.15:
            b_water_distribution = 0.15
            v_water_distribution_actual = Q_max1 / (b_water_distribution * B_pool)
        else:
            v_water_distribution_actual = v_water_distribution

        results['b_water_distribution'] = b_water_distribution
        results['v_water_distribution'] = v_water_distribution_actual

        # 6. 池体高度设计
        # 6.1 超高
        h1_sedimentation = 0.5
        results['h1_sedimentation'] = h1_sedimentation

        # 6.2 清水区高度
        h2_sedimentation = 1.0  # 取最大值
        results['h2_sedimentation'] = h2_sedimentation

        # 6.3 斜管高度（前面已计算）
        h3_sedimentation = results.get('h3_sedimentation', 0.866)  # 默认1.0m斜管

        # 6.4 缓冲区高度
        h4_sedimentation = 1.2  # 取最大值
        results['h4_sedimentation'] = h4_sedimentation

        # 6.5 泥斗设计
        # 确定泥斗下部直径
        for flow_limit, diameter in self.sludge_hopper_diameter_rules.items():
            if flow_rate <= flow_limit:
                d_sludge = diameter
                break

        # 确定泥斗高度
        for flow_limit, height in self.sludge_hopper_height_rules.items():
            if flow_rate <= flow_limit:
                h6_sedimentation = height
                break

        a_hopper = 75  # 泥斗角度，°
        # 计算泥斗上部直径
        D_sludge = d_sludge + 2 * (h6_sedimentation / math.tan(math.radians(a_hopper)))

        results['d_sludge'] = d_sludge
        results['h6_sedimentation'] = h6_sedimentation
        results['a_hopper'] = a_hopper
        results['D_sludge'] = D_sludge

        # 6.6 底坡高度
        a_slope = 10.5  # 底坡角度，°
        h5_sedimentation = (0.5 * B_pool - 0.5 * D_sludge) * math.tan(math.radians(a_slope))
        results['h5_sedimentation'] = h5_sedimentation
        results['a_slope'] = a_slope

        # 6.7 沉淀池总高
        h_total_sedimentation = (h1_sedimentation + h2_sedimentation + h3_sedimentation +
                                 h4_sedimentation + h5_sedimentation + h6_sedimentation)
        results['h_total_sedimentation'] = h_total_sedimentation

        # 6.8 过水板高度复核
        v_water_board_min = 0.02
        v_water_board_max = 0.03

        h_water_board_min = Q_max1 / (v_water_board_max * B_pool)
        h_water_board_max = Q_max1 / (v_water_board_min * B_pool)

        h_water_board = (h_water_board_min + h_water_board_max) / 2
        # 向上取整到10mm
        h_water_board = math.ceil(h_water_board * 1000 / 10) * 10 / 1000

        v_water_board_actual = Q_max1 / (h_water_board * B_pool)

        results['h_water_board'] = h_water_board
        results['v_water_board'] = v_water_board_actual
        results['v_water_board_in_range'] = 0.02 <= v_water_board_actual <= 0.03

        # 7. 出水三角堰及集水槽设计
        # 7.1 三角堰数量
        q_weir_load = 2.9 / 1000  # L/(s·m)转换为m³/(s·m)
        n_triangle_weir = Q_max1 / (B_pool * q_weir_load)

        if n_triangle_weir < 4:
            n_triangle_weir = 4
        else:
            # 向下偶数取整
            n_triangle_weir = int(n_triangle_weir)
            if n_triangle_weir % 2 != 0:
                n_triangle_weir -= 1

        results['n_triangle_weir'] = n_triangle_weir

        # 确定集水槽布置方式
        if n_triangle_weir == 4:
            layout_type = "环形布置"
            n_collection_tank = 4
        else:
            layout_type = "平行布置"
            n_collection_tank = n_triangle_weir // 2

        results['layout_type'] = layout_type
        results['n_collection_tank'] = n_collection_tank

        # 确定集水槽宽度
        for flow_limit, width in self.collection_tank_width_rules.items():
            if flow_rate <= flow_limit:
                b_collection_tank = width
                break

        # 确定三角堰口宽度
        for flow_limit, width in self.triangle_weir_width_rules.items():
            if flow_rate <= flow_limit:
                b_triangle_weir = width
                break

        results['b_collection_tank'] = b_collection_tank
        results['b_triangle_weir'] = b_triangle_weir

        # 计算三角堰长度
        if layout_type == "环形布置":
            l1_collection = L_pool - 2 * b_collection_tank
            l2_collection = L_pool - b_water_distribution - 2 * b_collection_tank
            n1_collection = 2
            n2_collection = 2
        else:  # 平行布置
            l1_collection = B_pool
            l2_collection = L_pool - b_water_distribution - b_collection_tank
            n1_collection = 1
            n2_collection = n_triangle_weir // 2

        # 三角堰口总数
        y_weir_openings = math.floor(l1_collection / b_triangle_weir) * n1_collection + math.floor(
            l2_collection / b_triangle_weir) * n2_collection
        results['y_weir_openings'] = y_weir_openings

        # 每个堰口的流量
        q_triangle_weir = Q_max1 / y_weir_openings
        results['q_triangle_weir'] = q_triangle_weir

        # 三角堰高度
        h_triangle_weir = b_triangle_weir / 2
        results['h_triangle_weir'] = h_triangle_weir

        # 堰上水头
        h_y_triangle_weir = (q_triangle_weir / 1.43) ** (2 / 5)
        results['h_y_triangle_weir'] = h_y_triangle_weir

        # 复核实际堰上负荷
        q_actual_weir_load = Q_max1 * 1000 / (y_weir_openings * b_triangle_weir)  # L/(s·m)
        results['q_actual_weir_load'] = q_actual_weir_load
        results['q_weir_load_check'] = q_actual_weir_load <= 5.8

        # 7.2 集水槽设计
        Q_single_collection_tank = Q_max1 / n_collection_tank

        # 临界水深
        h_k = (Q_single_collection_tank ** 2 / (9.81 * b_collection_tank ** 2)) ** (1 / 3)

        # 起端水深
        h_start = 1.73 * h_k

        # 水头损失
        delta_h_collection = h_start - h_k

        # 水位跌落高度
        if flow_rate <= 5000:
            h_drop = 0.12
        else:
            h_drop = 0.15

        # 集水槽总高度（防止溢流，按起端水深+跌落计算）
        h_total_collection = h_start + h_drop

        # 如果清水区高度过小（小于0.4m），改用理论公式
        if h2_sedimentation < 0.4:
            h_total_collection = 0.5 * (h_start + h_k) + h_drop

        results['h_total_collection'] = h_total_collection
        results['h_k'] = h_k
        results['h_start'] = h_start
        results['delta_h_collection'] = delta_h_collection
        results['h_drop'] = h_drop

        # 集水槽+三角堰总高
        h_collection_weir = h_total_collection + h_triangle_weir
        results['h_collection_weir'] = h_collection_weir

        # 8. 刮泥机功率复核
        # 8.1 最大排泥量计算
        n_scraper = sludge_recycle_ratio
        Q_sludge_dry = (flow_rate * (ss_in - ss_out + magnetic_powder_ratio * ss_in +
                                     (q_pac + q_pam) * n_scraper)) / (24 * 1000 * 1000)

        # 8.2 积泥量（含水率98%）
        sludge_moisture_content = 0.98
        Q_sludge_accumulated = Q_sludge_dry * 100 / (100 - sludge_moisture_content * 100)

        results['Q_sludge_dry'] = Q_sludge_dry
        results['Q_sludge_accumulated'] = Q_sludge_accumulated

        # 8.3 刮泥机旋转速度
        v_scraper = 2.4  # m/min
        r_scraper = v_scraper / (math.pi * B_pool)

        results['v_scraper'] = v_scraper
        results['r_scraper'] = r_scraper

        # 8.4 刮泥机功率
        density_sludge = 1.15  # t/m³
        friction_coefficient = 0.5
        efficiency_scraper = 0.8

        P_scraper = (9.81 * Q_sludge_accumulated * density_sludge *
                     friction_coefficient * 1000) / (60 * r_scraper)

        N_scraper = (2 / 3 * v_scraper * P_scraper) / (60000 * efficiency_scraper)

        # 电机选型（根据文档说明）
        if flow_rate > 5000:
            selected_scraper_power = 0.37
        else:
            selected_scraper_power = 0.25

        results['P_scraper'] = P_scraper
        results['N_scraper'] = N_scraper
        results['selected_scraper_power'] = selected_scraper_power

        results['adjustment_log'] = adjustment_log
        return results

    def calculate_single_stage_flocculation(self, ss_in, flow_rate, construction_type,
                                            d_inlet=None, inlet_type="泵入进水",q_max=None):
        """单级絮凝池参数计算"""
        results = {}
        adjustment_log = []

        # 水的密度
        water_density = 1150  # kg/m³

        # 1. 池体设计（与T2反应池池体设计公式一致）
        # 确定停留时间 t1（单级絮凝池特有规则）
        if ss_in >= 150:
            t1 = 120
        elif ss_in > 50:
            # 50<SS<150mg/L，90~120s，这里取中间值
            t1 = 105
        else:
            t1 = 90  # SS≤50mg/L
        results['t1'] = t1

        # 计算反应池体积 V1
        V1 = (flow_rate * t1) / (24 * 3600)
        results['V1'] = V1

        # 反应池尺寸确认（强制矩形池体）
        # 矩形池体
        l = (V1 / 1.5) ** (1 / 3)  # l=w, h2/D=1.5
        w = l
        D = math.sqrt((4 * l * w) / math.pi)
        h2 = 1.5 * D

        results['D'] = D
        results['l'] = l
        results['w'] = w
        results['h2'] = h2

        # 池体超高 h1
        h1 = 0.3 if construction_type == "钢结构" else 0.5
        results['h1'] = h1
        results['h_total'] = h1 + h2

        # 2. 折流混合区设计
        # ① 进水口设计
        if q_max is not None:
            Q_max1 = q_max / (24 * 3600)  # m³/s（使用 q_max）
        else:
            Q_max1 = flow_rate / (24 * 3600)  # 后备方案
        results['Q_max1'] = Q_max1

        if inlet_type == "泵入进水":
            # 泵入进水时，d_inlet由用户输入（单位mm）
            if d_inlet is None:
                d_inlet = 100  # 默认DN100
            d_inlet_m = d_inlet / 1000  # 转换为米
            S_inlet = math.pi * (d_inlet_m / 2) ** 2
            v_inlet = Q_max1 / S_inlet
        else:
            # 自流进水时，根据防淤流速反算口径
            v_target = 0.6  # 目标流速，取0.6m/s（按照要求修改）
            S_inlet = Q_max1 / v_target
            d_inlet_m = 2 * math.sqrt(S_inlet / math.pi)
            # 向上取整到标准管径
            d_inlet = math.ceil(d_inlet_m * 1000 / 10) * 10  # 向上取整到10mm
            d_inlet_m = d_inlet / 1000
            S_inlet = math.pi * (d_inlet_m / 2) ** 2
            v_inlet = Q_max1 / S_inlet

        results['d_inlet'] = d_inlet
        results['d_inlet_m'] = d_inlet_m
        results['S_inlet'] = S_inlet
        results['v_inlet'] = v_inlet
        results['inlet_type'] = inlet_type

        # ② 折流区设备参数计算
        # 折流区长度
        l_baffle = l
        results['l_baffle'] = l_baffle

        # 折流区宽度（通过停留时间反算）
        t_baffle = 30  # 折流区停留时间，s
        h2_baffle_initial = h2 * 0.8  # 初始估算值
        b_baffle = Q_max1 * t_baffle / (l_baffle * h2_baffle_initial)
        # 向上10mm取整
        b_baffle = math.ceil(b_baffle * 1000 / 10) * 10 / 1000
        results['b_baffle'] = b_baffle
        results['t_baffle'] = t_baffle

        # 折流板数量
        n_baffle = 4  # 默认4层
        results['n_baffle'] = n_baffle

        # 折流板间距
        b1_baffle = b_baffle  # 优先取1倍折流区宽度
        results['b1_baffle'] = b1_baffle

        # 底层折板距离底高度
        h_baffle_bottom = 1.5 * b_baffle  # 优先1.5倍
        results['h_baffle_bottom'] = h_baffle_bottom

        # 顶部折流板距离水面高度
        h_baffle_top = l_baffle / 4  # 优先1/4倍
        results['h_baffle_top'] = h_baffle_top

        # 计算折流区有效高度
        h2_baffle = h_baffle_bottom + b1_baffle * (n_baffle - 1) + h_baffle_top
        results['h2_baffle'] = h2_baffle

        # 扰流板高度
        h_disturb = 0.2 * b1_baffle
        results['h_disturb'] = h_disturb

        # 下部扰流板个数
        n_disturb = math.floor(l_baffle / b1_baffle)
        results['n_disturb'] = n_disturb

        # 顶部扰流板个数
        n_disturb_top = n_disturb - 1
        results['n_disturb_top'] = n_disturb_top

        # 扰流板总数量
        n_disturb_total = n_baffle * n_disturb - 1
        results['n_disturb_total'] = n_disturb_total

        # 3. 单级混絮凝搅拌设计
        # 外缘线速度（单级絮凝池特有规则）
        if ss_in >= 150:
            v1 = 4.2
        elif ss_in > 50:
            v1 = 3.7
        else:
            v1 = 3.2
        results['v1'] = v1

        # 搅拌直径确定（与T2反应池计算一致）
        if ss_in >= 500:
            d1_ratio = 0.5
        elif ss_in > 100:
            d1_ratio = 1 / 3 + (ss_in - 100) * (1 / 2 - 1 / 3) / 400
        else:
            d1_ratio = 1 / 3

        d1 = d1_ratio * D
        # 向上取整到10mm
        d1 = math.ceil(d1 * 100) / 100
        results['d1'] = d1

        # 复核 S1/S 范围
        S = l * w
        S1 = (math.pi * d1 ** 2) / 4
        s1_s_ratio = S1 / S
        results['S1_S_ratio'] = s1_s_ratio
        results['S1_S_in_range'] = s1_s_ratio < 0.25

        # 自动调整S1/S比例
        if not results['S1_S_in_range']:
            original_d1 = d1
            max_iterations = 50
            iteration = 0
            while not results['S1_S_in_range'] and iteration < max_iterations:
                iteration += 1
                if s1_s_ratio >= 0.25:
                    d1 *= 0.95  # 减小直径

                S1 = (math.pi * d1 ** 2) / 4
                s1_s_ratio = S1 / S
                results['S1_S_in_range'] = s1_s_ratio < 0.25

            if iteration > 0:
                adjustment_log.append(f"自动调整搅拌直径: 从 {original_d1:.3f}m 调整为 {d1:.3f}m")
                results['d1'] = d1
                results['S1_S_ratio'] = s1_s_ratio

        # 搅拌器桨叶宽度
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

        # 搅拌功率计算
        n1 = (60 * v1) / (math.pi * d1)
        results['n1'] = n1

        w1 = (2 * v1) / d1
        results['w1'] = w1

        # 搅拌层数
        h2_D_ratio = h2 / D
        e = 2 if h2_D_ratio > 1.3 else 1
        results['e'] = e

        R1 = 0.5 * d1

        N1 = (self.resistance_coefficient * water_density * (w1 ** 3) *
              self.paddle_blades * e * b * (R1 ** 4) * math.sin(math.radians(self.paddle_angle))) / (408 * self.gravity)
        results['N1'] = N1

        # 电动机功率
        Na1 = (self.motor_condition_factor * N1) / (self.reducer_efficiency * self.bearing_efficiency)
        results['Na1'] = Na1

        # 电动机选型功率
        selected_motor_power = self.select_motor_power(Na1)
        results['selected_motor_power'] = selected_motor_power

        # 速度梯度复核
        G1 = math.sqrt((1000 * N1) / (self.dynamic_viscosity * Q_max1 * t1))
        results['G1'] = G1
        results['G1_in_range'] = 200 <= G1 <= 500
        results['G1_range'] = (200, 500)

        # 自动调整速度梯度
        if not results['G1_in_range']:
            original_v1 = v1
            max_iterations = 50
            iteration = 0
            while not results['G1_in_range'] and iteration < max_iterations:
                iteration += 1

                if G1 < 200:  # 低于下限
                    v1 *= 1.05  # 增加线速度
                elif G1 > 500:  # 高于上限
                    v1 *= 0.95  # 减小线速度

                # 重新计算所有相关参数
                n1 = (60 * v1) / (math.pi * d1)
                w1 = (2 * v1) / d1
                N1 = (self.resistance_coefficient * water_density * (w1 ** 3) *
                      self.paddle_blades * e * b * (R1 ** 4) * math.sin(math.radians(self.paddle_angle))) / (
                                 408 * self.gravity)

                G1 = math.sqrt((1000 * N1) / (self.dynamic_viscosity * Q_max1 * t1))
                results['G1_in_range'] = 200 <= G1 <= 500

            if iteration > 0:
                adjustment_log.append(f"自动调整线速度: 从 {original_v1:.2f}m/s 调整为 {v1:.2f}m/s")
                results['v1'] = v1
                results['G1'] = G1
                results['n1'] = n1
                results['w1'] = w1
                results['N1'] = N1
                results['Na1'] = (self.motor_condition_factor * N1) / (
                            self.reducer_efficiency * self.bearing_efficiency)
                results['selected_motor_power'] = self.select_motor_power(results['Na1'])

        # 新增：桨叶间距复核（与T3一致）
        # 下层桨叶距离池底距离
        if construction_type == "钢结构":
            l1 = 0.5 * d1
        else:
            l1 = 1.0 * d1
        results['l1'] = l1

        # 上层与下层桨叶间距（按照要求修改为1*d1）
        l2 = 1.0 * d1  # 按照要求修改为1*d1
        results['l2'] = l2

        # 桨叶距离水面距离复核
        distance_to_surface = h2 - l1 - l2
        results['distance_to_surface'] = distance_to_surface

        # 检查是否满足 0.5~1倍桨叶直径
        required_min = 0.5 * d1
        required_max = 1.0 * d1
        results['distance_surface_in_range'] = required_min <= distance_to_surface <= required_max
        results['distance_surface_range'] = (required_min, required_max)

        # 4. 单级混絮凝导流筒设计
        # 导流筒直径
        D_d = D * 1.1
        results['D_d'] = D_d

        # 导流筒覆盖面积比值
        S_d = math.pi * (D_d / 2) ** 2
        S_pool = l * w
        Y_guide = S_d / S_pool
        results['S_d'] = S_d
        results['S_pool'] = S_pool
        results['Y_guide'] = Y_guide
        results['Y_guide_in_range'] = 0.15 <= Y_guide <= 0.20

        # 絮凝回流比
        l1_single = 1.5 * d1  # 两层桨叶间的间距
        r_guide = (1.05 * (d1 / D_d) ** 0.848 * (b / D_d) ** 0.413 *
                   e ** 0.375 * (l1_single / D_d) ** 0.762 *
                   (n1 / 60) * D_d ** 3) / Q_max1
        results['l1_single'] = l1_single
        results['r_guide'] = r_guide

        # 导流筒高度
        h_guide_total = h2 / 2
        results['h_guide_total'] = h_guide_total

        # 导流筒喇叭口高度
        h_horn = 0.3  # 经验值
        results['h_horn'] = h_horn

        # 5. 底部导流板参数设计
        # 导流筒下部导流板高度
        h_guide_plate = h2 / 2
        results['h_guide_plate'] = h_guide_plate

        # 导流板宽度
        b_guide_plate = h_guide_plate / 2
        results['b_guide_plate'] = b_guide_plate

        # 导流板数量
        n_guide_plate = 6  # 统一采用6块
        results['n_guide_plate'] = n_guide_plate

        # 6. 流速校核
        # 导流筒内设计流量
        Q_n = (r_guide + 1) * Q_max1
        results['Q_n'] = Q_n

        # 导流筒内流速
        v1_guide = Q_n / S_d
        results['v1_guide'] = v1_guide

        # 导流筒上缘污水入口前速度
        h_guide_top = h2 - h_guide_total - h_guide_plate
        # 确保h_guide_top不为零
        if h_guide_top <= 0:
            h_guide_top = 0.1  # 设置一个最小安全值

        v2_upper = Q_n / (h_guide_top * D_d * math.pi)
        results['h_guide_top'] = h_guide_top
        results['v2_upper'] = v2_upper

        # 导流筒外喇叭口以上部分流速
        v3_above_horn = Q_n / (S_pool - S_d)
        results['v3_above_horn'] = v3_above_horn

        # 导流筒外喇叭口处时的流速
        D_d1 = D_d + 2 * h_horn * math.cos(math.radians(60))  # cot(60°) = cos(60°)/sin(60°)
        S_d1 = math.pi * (D_d1 / 2) ** 2
        v4_horn = Q_n / (S_pool - S_d1)
        results['D_d1'] = D_d1
        results['S_d1'] = S_d1
        results['v4_horn'] = v4_horn

        # 导流筒喇叭口以下部分流速
        v5_below = Q_n / (h_guide_plate * D_d1 * math.pi)
        results['v5_below'] = v5_below

        # 流速校核结果
        velocities = [v2_upper, v3_above_horn, v4_horn, v5_below]
        velocity_diff = max(velocities) - min(velocities)
        results['velocity_diff'] = velocity_diff
        results['velocity_check_ok'] = velocity_diff < 0.5  # 假设差值小于0.5m/s为良好

        results['adjustment_log'] = adjustment_log
        return results
    # 其他现有的计算函数（T1, T2, T3）保持不变
    # ... [这里省略了T1, T2, T3的计算函数以节省空间，实际代码中需要保留]
    def calculate_t1_parameters(self, ss_in, flow_rate, construction_type, pool_shape,
                                l=None, w=None, h2=None, d1=None, v1=None, calculation_mode="正向计算"):
        """T1反应池参数计算"""
        results = {}
        adjustment_log = []  # 记录调整过程

        # 水的密度
        water_density = 1050  # kg/m³

        if calculation_mode == "正向计算":
            # 正向计算：根据SS确定停留时间，然后计算体积和尺寸
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
        else:
            # 反向计算：根据给定的尺寸计算体积和停留时间
            if pool_shape == "圆形":
                # 圆形池体
                D = l  # 在圆形情况下，l存储的是直径D
                V1 = (math.pi * D ** 2 / 4) * h2
                l = None
                w = None
            else:
                # 矩形池体
                V1 = l * w * h2
                D = math.sqrt((4 * l * w) / math.pi)

            results['V1'] = V1
            # 反推停留时间 t1
            t1 = (V1 * 24 * 3600) / flow_rate
            results['t1'] = t1

        results['D'] = D
        results['l'] = l
        results['w'] = w
        results['h2'] = h2

        # 调用通用计算函数完成剩余计算
        self._calculate_common_parameters(results, ss_in, flow_rate, construction_type, pool_shape,
                                          water_density, d1, v1, "T1", adjustment_log)

        results['adjustment_log'] = adjustment_log
        return results

    def calculate_t2_parameters(self, ss_in, flow_rate, construction_type, pool_shape,
                                l=None, w=None, h2=None, d1=None, v1=None, calculation_mode="正向计算"):
        """T2反应池参数计算"""
        results = {}
        adjustment_log = []  # 记录调整过程

        # 水的密度
        water_density = 1150  # kg/m³

        if calculation_mode == "正向计算":
            # 正向计算：根据SS确定停留时间，然后计算体积和尺寸
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
        else:
            # 反向计算：根据给定的尺寸计算体积和停留时间
            if pool_shape == "圆形":
                # 圆形池体
                D = l  # 在圆形情况下，l存储的是直径D
                V1 = (math.pi * D ** 2 / 4) * h2
                l = None
                w = None
            else:
                # 矩形池体
                V1 = l * w * h2
                D = math.sqrt((4 * l * w) / math.pi)

            results['V1'] = V1
            # 反推停留时间 t1
            t1 = (V1 * 24 * 3600) / flow_rate
            results['t1'] = t1

        results['D'] = D
        results['l'] = l
        results['w'] = w
        results['h2'] = h2

        # 调用通用计算函数完成剩余计算
        self._calculate_common_parameters(results, ss_in, flow_rate, construction_type, pool_shape,
                                          water_density, d1, v1, "T2", adjustment_log)

        results['adjustment_log'] = adjustment_log
        return results

    def calculate_t3_parameters(self, ss_in, flow_rate, construction_type, pool_shape,
                                l=None, w=None, h2=None, d_lower=None, v_lower=None, calculation_mode="正向计算"):
        """T3差速搅拌反应池参数计算"""
        results = {}
        adjustment_log = []  # 记录调整过程

        # 水的密度
        water_density = 1150  # kg/m³

        if calculation_mode == "正向计算":
            # 正向计算：根据SS确定停留时间，然后计算体积和尺寸
            # ① 确定停留时间 t1 (T3特有的规则)
            if ss_in >= 150:
                t1 = 200
            elif ss_in > 100:
                # 50<SS≤100时，180-200s，线性相关
                t1 = 180 + (ss_in - 50) * (200 - 180) / 50
            elif ss_in > 50:
                # 50<SS≤100时，180-200s，线性相关
                t1 = 180 + (ss_in - 50) * (200 - 180) / 50
            else:
                t1 = 180  # SS≤50
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
        else:
            # 反向计算：根据给定的尺寸计算体积和停留时间
            if pool_shape == "圆形":
                # 圆形池体
                D = l  # 在圆形情况下，l存储的是直径D
                V1 = (math.pi * D ** 2 / 4) * h2
                l = None
                w = None
            else:
                # 矩形池体
                V1 = l * w * h2
                D = math.sqrt((4 * l * w) / math.pi)

            results['V1'] = V1
            # 反推停留时间 t1
            t1 = (V1 * 24 * 3600) / flow_rate
            results['t1'] = t1

        results['D'] = D
        results['l'] = l
        results['w'] = w
        results['h2'] = h2

        # 调用T3专用计算函数
        self._calculate_t3_parameters(results, ss_in, flow_rate, construction_type, pool_shape,
                                      water_density, d_lower, v_lower, adjustment_log)

        results['adjustment_log'] = adjustment_log
        return results

    def _calculate_t3_parameters(self, results, ss_in, flow_rate, construction_type, pool_shape,
                                 water_density, d_lower=None, v_lower=None, adjustment_log=None):
        """T3差速搅拌反应池专用参数计算"""
        if adjustment_log is None:
            adjustment_log = []

        # 池体超高 h1
        h1 = 0.3 if construction_type == "钢结构" else 0.5
        results['h1'] = h1
        results['h_total'] = h1 + results['h2']

        # ④ T3差速搅拌池线速度确定
        # 下层桨叶线速度
        if v_lower is None:
            if ss_in <= 250:
                v_lower = 2.8
            elif ss_in <= 400:
                v_lower = 3.0
            else:
                v_lower = 3.2
        results['v_lower'] = v_lower

        # 上层桨叶线速度 (上层线速度 = 3/4 × 下层线速度)
        v_upper = 0.75 * v_lower
        results['v_upper'] = v_upper

        # ⑤ 搅拌直径确定
        # 下层桨叶直径 (与T1T2计算一致)
        if d_lower is None:
            if ss_in >= 500:
                d_lower_ratio = 0.5
            elif ss_in > 100:
                # 线性相关
                d_lower_ratio = 1 / 3 + (ss_in - 100) * (1 / 2 - 1 / 3) / 400
            else:
                d_lower_ratio = 1 / 3

            d_lower = d_lower_ratio * results['D']
            # 向上取整到10mm
            d_lower = math.ceil(d_lower * 100) / 100

        results['d_lower'] = d_lower

        # 上层桨叶直径 (根据转速公式推导)
        d_upper = (v_upper * d_lower) / v_lower
        results['d_upper'] = d_upper

        # 复核 S1/S 范围
        if pool_shape == "圆形":
            S = (math.pi * results['D'] ** 2) / 4
        else:
            S = results['l'] * results['w'] if results['l'] and results['w'] else 0

        # 下层桨叶面积复核
        S1_lower = (math.pi * d_lower ** 2) / 4
        s1_s_ratio_lower = S1_lower / S
        results['S1_S_ratio_lower'] = s1_s_ratio_lower
        results['S1_S_in_range_lower'] = s1_s_ratio_lower < 0.2

        # 上层桨叶面积复核
        S1_upper = (math.pi * d_upper ** 2) / 4
        s1_s_ratio_upper = S1_upper / S
        results['S1_S_ratio_upper'] = s1_s_ratio_upper
        results['S1_S_in_range_upper'] = s1_s_ratio_upper < 0.12

        # 自动调整S1/S比例
        if not results['S1_S_in_range_lower'] or not results['S1_S_in_range_upper']:
            original_d_lower = d_lower
            # 调整下层直径直到满足要求
            max_iterations = 50
            iteration = 0
            while (not results['S1_S_in_range_lower'] or not results[
                'S1_S_in_range_upper']) and iteration < max_iterations:
                iteration += 1
                # 根据面积比调整直径
                if s1_s_ratio_lower >= 0.2:
                    d_lower *= 0.95  # 减小直径
                elif s1_s_ratio_upper >= 0.12:
                    d_lower *= 0.95  # 减小直径

                # 更新上层直径
                d_upper = (v_upper * d_lower) / v_lower

                # 重新计算面积比
                S1_lower = (math.pi * d_lower ** 2) / 4
                s1_s_ratio_lower = S1_lower / S
                S1_upper = (math.pi * d_upper ** 2) / 4
                s1_s_ratio_upper = S1_upper / S

                results['S1_S_in_range_lower'] = s1_s_ratio_lower < 0.2
                results['S1_S_in_range_upper'] = s1_s_ratio_upper < 0.12

            if iteration > 0:
                adjustment_log.append(f"自动调整搅拌直径: 下层直径从 {original_d_lower:.3f}m 调整为 {d_lower:.3f}m")
                adjustment_log.append(f"上层直径相应调整为 {d_upper:.3f}m")
                results['d_lower'] = d_lower
                results['d_upper'] = d_upper
                results['S1_S_ratio_lower'] = s1_s_ratio_lower
                results['S1_S_ratio_upper'] = s1_s_ratio_upper

        # 桨叶宽度确定 (上下层分别确定)
        # 下层桨叶宽度
        if d_lower <= 0.5:
            b_lower = 0.10
        elif d_lower < 1:
            b_lower = 0.15
        elif d_lower < 1.6:
            b_lower = 0.20
        elif d_lower < 2:
            b_lower = 0.25
        else:
            b_lower = 0.30
        results['b_lower'] = b_lower

        # 上层桨叶宽度
        if d_upper <= 0.5:
            b_upper = 0.10
        elif d_upper < 1:
            b_upper = 0.15
        elif d_upper < 1.6:
            b_upper = 0.20
        elif d_upper < 2:
            b_upper = 0.25
        else:
            b_upper = 0.30
        results['b_upper'] = b_upper

        # ⑥ 搅拌功率计算
        # 下层搅拌功率
        n_lower = (60 * v_lower) / (math.pi * d_lower)
        results['n_lower'] = n_lower

        w_lower = (2 * v_lower) / d_lower
        results['w_lower'] = w_lower

        R_lower = 0.5 * d_lower
        e = 1  # 差速搅拌计算时，e取1

        N_lower = (self.resistance_coefficient * water_density * (w_lower ** 3) *
                   self.paddle_blades * e * b_lower * (R_lower ** 4) *
                   math.sin(math.radians(self.paddle_angle))) / (408 * self.gravity)
        results['N_lower'] = N_lower

        # 下层电动机功率
        Na_lower = (self.motor_condition_factor * N_lower) / (self.reducer_efficiency * self.bearing_efficiency)
        results['Na_lower'] = Na_lower

        # 下层电动机选型功率
        selected_motor_power_lower = self.select_motor_power(Na_lower)
        results['selected_motor_power_lower'] = selected_motor_power_lower

        # 上层搅拌功率
        n_upper = n_lower  # 上下层同轴，转速一致
        results['n_upper'] = n_upper

        w_upper = (2 * v_upper) / d_upper
        results['w_upper'] = w_upper

        R_upper = 0.5 * d_upper

        N_upper = (self.resistance_coefficient * water_density * (w_upper ** 3) *
                   self.paddle_blades * e * b_upper * (R_upper ** 4) *
                   math.sin(math.radians(self.paddle_angle))) / (408 * self.gravity)
        results['N_upper'] = N_upper

        # 上层电动机功率
        Na_upper = (self.motor_condition_factor * N_upper) / (self.reducer_efficiency * self.bearing_efficiency)
        results['Na_upper'] = Na_upper

        # 上层电动机选型功率
        selected_motor_power_upper = self.select_motor_power(Na_upper)
        results['selected_motor_power_upper'] = selected_motor_power_upper

        # 差速搅拌总功率
        N_total = Na_lower + Na_upper
        results['N_total'] = N_total

        # 总电动机选型功率
        selected_motor_power_total = self.select_motor_power(N_total)
        results['selected_motor_power_total'] = selected_motor_power_total

        # 速度梯度复核
        Q_max1 = flow_rate / (24 * 3600)  # m³/s

        # 下层速度梯度
        G_lower = math.sqrt((1000 * N_lower) / (self.dynamic_viscosity * Q_max1 * results['t1']))
        results['G_lower'] = G_lower
        results['G_lower_in_range'] = 100 <= G_lower <= 300
        results['G_lower_range'] = (100, 300)

        # 上层速度梯度
        G_upper = math.sqrt((1000 * N_upper) / (self.dynamic_viscosity * Q_max1 * results['t1']))
        results['G_upper'] = G_upper
        results['G_upper_in_range'] = 50 <= G_upper <= 150
        results['G_upper_range'] = (50, 150)

        # 自动调整速度梯度
        if not results['G_lower_in_range'] or not results['G_upper_in_range']:
            original_v_lower = v_lower
            # 调整线速度直到满足要求
            max_iterations = 50
            iteration = 0
            while (not results['G_lower_in_range'] or not results['G_upper_in_range']) and iteration < max_iterations:
                iteration += 1

                # 根据梯度调整线速度
                if G_lower < 100 or G_upper < 50:
                    v_lower *= 1.05  # 增加线速度
                elif G_lower > 300 or G_upper > 150:
                    v_lower *= 0.95  # 减小线速度

                # 更新上层线速度
                v_upper = 0.75 * v_lower

                # 重新计算所有相关参数
                n_lower = (60 * v_lower) / (math.pi * d_lower)
                w_lower = (2 * v_lower) / d_lower
                N_lower = (self.resistance_coefficient * water_density * (w_lower ** 3) *
                           self.paddle_blades * e * b_lower * (R_lower ** 4) *
                           math.sin(math.radians(self.paddle_angle))) / (408 * self.gravity)

                n_upper = n_lower
                w_upper = (2 * v_upper) / d_upper
                N_upper = (self.resistance_coefficient * water_density * (w_upper ** 3) *
                           self.paddle_blades * e * b_upper * (R_upper ** 4) *
                           math.sin(math.radians(self.paddle_angle))) / (408 * self.gravity)

                # 重新计算速度梯度
                G_lower = math.sqrt((1000 * N_lower) / (self.dynamic_viscosity * Q_max1 * results['t1']))
                G_upper = math.sqrt((1000 * N_upper) / (self.dynamic_viscosity * Q_max1 * results['t1']))

                results['G_lower_in_range'] = 100 <= G_lower <= 300
                results['G_upper_in_range'] = 50 <= G_upper <= 150

            if iteration > 0:
                adjustment_log.append(f"自动调整线速度: 下层线速度从 {original_v_lower:.2f}m/s 调整为 {v_lower:.2f}m/s")
                adjustment_log.append(f"上层线速度相应调整为 {v_upper:.2f}m/s")
                results['v_lower'] = v_lower
                results['v_upper'] = v_upper
                results['G_lower'] = G_lower
                results['G_upper'] = G_upper
                # 更新其他相关参数
                results['n_lower'] = n_lower
                results['w_lower'] = w_lower
                results['N_lower'] = N_lower
                results['n_upper'] = n_upper
                results['w_upper'] = w_upper
                results['N_upper'] = N_upper
                results['Na_lower'] = (self.motor_condition_factor * N_lower) / (
                            self.reducer_efficiency * self.bearing_efficiency)
                results['Na_upper'] = (self.motor_condition_factor * N_upper) / (
                            self.reducer_efficiency * self.bearing_efficiency)
                results['N_total'] = results['Na_lower'] + results['Na_upper']
                results['selected_motor_power_total'] = self.select_motor_power(results['N_total'])

        # ⑦ 桨叶间距复核
        # 下层桨叶距离池底距离
        if construction_type == "钢结构":
            l1 = 0.5 * d_lower
        else:
            l1 = 1.0 * d_lower
        results['l1'] = l1

        # 上层与下层桨叶间距
        if construction_type == "钢结构":
            l2 = 1.0 * d_upper
        else:
            l2 = 1.5 * d_upper
        results['l2'] = l2

        # 上层桨叶距离水面距离复核
        distance_to_surface = results['h2'] - l1 - l2
        results['distance_to_surface'] = distance_to_surface

        # 检查是否满足 0.5~1倍上层桨叶直径
        required_min = 0.5 * d_upper
        required_max = 1.0 * d_upper
        results['distance_surface_in_range'] = required_min <= distance_to_surface <= required_max
        results['distance_surface_range'] = (required_min, required_max)

    def _calculate_common_parameters(self, results, ss_in, flow_rate, construction_type, pool_shape,
                                     water_density, d1=None, v1=None, reactor_type="T1", adjustment_log=None):
        """通用参数计算（T1和T2反应池共用）"""
        if adjustment_log is None:
            adjustment_log = []

        # 池体超高 h1
        h1 = 0.3 if construction_type == "钢结构" else 0.5
        results['h1'] = h1
        results['h_total'] = h1 + results['h2']
        # 新增：设备总高度计算（用于沉淀池高程设计）
        if construction_type == "钢结构":
            h_base = 0.1  # 钢结构底板高度
        else:
            # 土建结构，需要用户输入或采用默认值
            h_base = 0.3  # 默认土建底板高度

        h_equipment_total = results['h_total'] + h_base
        results['h_base'] = h_base
        results['h_equipment_total'] = h_equipment_total
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

        # 自动调整S1/S比例
        if not results['S1_S_in_range']:
            original_d1 = d1
            # 调整直径直到满足要求
            max_iterations = 50
            iteration = 0
            while not results['S1_S_in_range'] and iteration < max_iterations:
                iteration += 1
                # 根据面积比调整直径
                if s1_s_ratio >= 0.25:
                    d1 *= 0.95  # 减小直径

                # 重新计算面积比
                S1 = (math.pi * d1 ** 2) / 4
                s1_s_ratio = S1 / S
                results['S1_S_in_range'] = s1_s_ratio < 0.25

            if iteration > 0:
                adjustment_log.append(f"自动调整搅拌直径: 从 {original_d1:.3f}m 调整为 {d1:.3f}m")
                results['d1'] = d1
                results['S1_S_ratio'] = s1_s_ratio

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

        # 自动调整速度梯度
        if not results['G1_in_range']:
            original_v1 = v1
            # 调整线速度直到满足要求
            max_iterations = 50
            iteration = 0
            while not results['G1_in_range'] and iteration < max_iterations:
                iteration += 1

                # 根据梯度调整线速度
                if G1 < results['G1_range'][0]:  # 低于下限
                    v1 *= 1.05  # 增加线速度
                elif G1 > results['G1_range'][1]:  # 高于上限
                    v1 *= 0.95  # 减小线速度

                # 重新计算所有相关参数
                n1 = (60 * v1) / (math.pi * d1)
                w1 = (2 * v1) / d1
                N1 = (self.resistance_coefficient * water_density * (w1 ** 3) *
                      self.paddle_blades * e * b * (R1 ** 4) * math.sin(math.radians(self.paddle_angle))) / (
                                 408 * self.gravity)

                # 重新计算速度梯度
                G1 = math.sqrt((1000 * N1) / (self.dynamic_viscosity * Q_max1 * results['t1']))
                results['G1_in_range'] = results['G1_range'][0] <= G1 <= results['G1_range'][1]

            if iteration > 0:
                adjustment_log.append(f"自动调整线速度: 从 {original_v1:.2f}m/s 调整为 {v1:.2f}m/s")
                results['v1'] = v1
                results['G1'] = G1
                # 更新其他相关参数
                results['n1'] = n1
                results['w1'] = w1
                results['N1'] = N1
                results['Na1'] = (self.motor_condition_factor * N1) / (
                            self.reducer_efficiency * self.bearing_efficiency)
                results['selected_motor_power'] = self.select_motor_power(results['Na1'])

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

    # 反应池类型选择 - 增加单级絮凝池
    reactor_type = st.sidebar.selectbox(
        "反应池类型",
        ["T1反应池", "T2反应池", "T3反应池", "单级絮凝池","沉淀池"],
        help="选择要计算的反应池类型"
    )
    # 沉淀池特有的参数输入
    if reactor_type == "沉淀池":
        st.sidebar.subheader("沉淀池参数")

        calculation_mode = st.sidebar.selectbox(
            "计算模式",
            ["正向计算", "反向计算"],
            help="正向计算：根据水质参数计算池体尺寸\n反向计算：根据池体尺寸验证设计参数"
        )

        if calculation_mode == "正向计算":
            # 正向计算：根据处理量计算
            total_height_input = st.sidebar.number_input(
                "沉淀池预估总高 (m)",
                min_value=2.0,
                max_value=10.0,
                value=4.0,
                help="用于选择斜管长度"
            )
            pool_length = None
            pool_width = None
            tube_utilization = None
        else:
            # 反向计算：输入已有池体尺寸
            pool_length = st.sidebar.number_input("池体长度 L (m)", min_value=1.0, value=4.0)
            pool_width = st.sidebar.number_input("池体宽度 B (m)", min_value=1.0, value=4.0)
            tube_utilization = st.sidebar.number_input("斜管利用率", min_value=0.7, max_value=1.0, value=0.85)
            total_height_input = None

        # 药剂和污泥参数
        st.sidebar.subheader("药剂及污泥参数")
        q_pac = st.sidebar.number_input("PAC投加量 (mg/L)", min_value=0.0, value=50.0)
        q_pam = st.sidebar.number_input("PAM投加量 (mg/L)", min_value=0.0, value=2.0)
        sludge_recycle_ratio = st.sidebar.number_input("污泥回流比", min_value=1.0, value=1.53)
        magnetic_powder_ratio = st.sidebar.number_input("磁粉投加倍数", min_value=3.0, max_value=5.0, value=5.0)

        # 沉淀池不需要以下参数，设置为默认值
        construction_type = "钢结构"  # 沉淀池通常为钢结构
        pool_shape = "矩形"  # 沉淀池为矩形

    # 计算模式选择 - 单级絮凝池只有正向计算
    elif reactor_type == "单级絮凝池":
        calculation_mode = "正向计算"
        st.sidebar.info("单级絮凝池只支持正向计算模式")
    else:
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

    # 单级絮凝池特有的参数
    if reactor_type == "单级絮凝池":
        inlet_type = st.sidebar.selectbox("进水类型", ["泵入进水", "自流进水"])
        if inlet_type == "泵入进水":
            d_inlet = st.sidebar.number_input("进水口口径 (mm)", min_value=50, value=100, step=10)
        else:
            d_inlet = None
        # 单级絮凝池强制为矩形池体
        pool_shape = "矩形"
        st.sidebar.info("单级絮凝池采用矩形池体设计")
    else:
        pool_shape = st.sidebar.selectbox("反应池池体形状", ["圆形", "矩形"])
        inlet_type = "泵入进水"
        d_inlet = None

    # 初始化变量，避免未绑定错误
    l, w, h2 = None, None, None

    # 反向计算专用输入（单级絮凝池不需要）
    if calculation_mode == "反向计算" and reactor_type != "单级絮凝池":
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

        # 在计算按钮的处理逻辑中添加沉淀池分支
        if reactor_type == "沉淀池":
            st.info(f"🔍 {calculation_mode}计算模式：沉淀池参数计算")

            # 获取T1池的设备总高度（如果有的话）
            t1_equipment_height = None
            if 't1_results' in st.session_state and st.session_state.t1_results:
                t1_equipment_height = st.session_state.t1_results.get('h_equipment_total')

            # 调用沉淀池计算方法
            sedimentation_results = calculator.calculate_sedimentation_pool(
                flow_rate, construction_type, total_height_input,
                pool_length, pool_width, tube_utilization, calculation_mode,
                q_pac, q_pam, ss_in, ss_out, sludge_recycle_ratio, magnetic_powder_ratio,q_max
            )

            # 将沉淀池结果也赋值给t1_results，以便后续统一处理
            t1_results = sedimentation_results

            # 保存计算结果到会话状态
            st.session_state.t1_results = sedimentation_results
            st.session_state.calculation_completed = True
            st.session_state.reactor_type = reactor_type
            st.session_state.flow_selection = flow_selection
            st.session_state.calculation_mode = calculation_mode
            st.session_state.pool_shape = pool_shape
            st.session_state.q0 = q0
            st.session_state.q_max = q_max
            st.session_state.flow_rate = flow_rate
            st.session_state.flow_display_name = flow_display_name
            st.session_state.l = l
            st.session_state.w = w

            # 对于沉淀池，设置show_adjustment为False，避免进入手动调整界面
            st.session_state.show_adjustment = False

            # 显示沉淀池结果
            display_sedimentation_results(sedimentation_results, flow_rate, calculation_mode)

            # 显示调整日志（如果有）
            if sedimentation_results.get('adjustment_log'):
                st.header("🔄 自动调整记录")
                for log in sedimentation_results['adjustment_log']:
                    st.info(log)

            # 直接返回，避免执行后续的反应池检查逻辑
            return


        elif reactor_type == "单级絮凝池":
            st.info("🔍 单级絮凝池正向计算模式")
            t1_results = calculator.calculate_single_stage_flocculation(
                ss_in, flow_rate, construction_type, d_inlet, inlet_type,q_max
            )
        elif calculation_mode == "正向计算":
            st.info(f"🔍 正向计算模式：根据水质参数计算{reactor_type}池体尺寸")
            # 这里调用原有的T1, T2, T3计算函数
            # 为简洁起见，省略具体实现
            if reactor_type == "T1反应池":
                t1_results = calculator.calculate_t1_parameters(
                    ss_in, flow_rate, construction_type, pool_shape,
                    calculation_mode=calculation_mode
                )
            elif reactor_type == "T2反应池":
                t1_results = calculator.calculate_t2_parameters(
                    ss_in, flow_rate, construction_type, pool_shape,
                    calculation_mode=calculation_mode
                )
            else:  # T3反应池
                t1_results = calculator.calculate_t3_parameters(
                    ss_in, flow_rate, construction_type, pool_shape,
                    calculation_mode=calculation_mode
                )
        else:
            st.info(f"🔍 反向计算模式：根据池体尺寸验证{reactor_type}水力停留时间")
            # 这里调用原有的T1, T2, T3反向计算函数
            # 为简洁起见，省略具体实现
            if l is None or h2 is None:
                st.error("❌ 反向计算需要输入池体尺寸参数")
                st.stop()

            if reactor_type == "T1反应池":
                t1_results = calculator.calculate_t1_parameters(
                    ss_in, flow_rate, construction_type, pool_shape,
                    l, w, h2, calculation_mode=calculation_mode
                )
            elif reactor_type == "T2反应池":
                t1_results = calculator.calculate_t2_parameters(
                    ss_in, flow_rate, construction_type, pool_shape,
                    l, w, h2, calculation_mode=calculation_mode
                )
            else:  # T3反应池
                t1_results = calculator.calculate_t3_parameters(
                    ss_in, flow_rate, construction_type, pool_shape,
                    l, w, h2, calculation_mode=calculation_mode
                )

        # 保存计算结果到会话状态
        st.session_state.t1_results = t1_results
        st.session_state.calculation_completed = True
        st.session_state.flow_selection = flow_selection
        st.session_state.calculation_mode = calculation_mode
        st.session_state.pool_shape = pool_shape
        st.session_state.q0 = q0
        st.session_state.q_max = q_max
        st.session_state.flow_rate = flow_rate
        st.session_state.flow_display_name = flow_display_name
        st.session_state.l = l
        st.session_state.w = w
        st.session_state.reactor_type = reactor_type

        # 显示自动调整日志
        if t1_results.get('adjustment_log'):
            st.header("🔄 自动调整记录")
            for log in t1_results['adjustment_log']:
                st.info(log)

        # 检查关键参数是否在范围内
        if reactor_type == "单级絮凝池":
            # 检查速度梯度
            g1_min, g1_max = t1_results['G1_range']
            if not t1_results['G1_in_range']:
                st.session_state.show_adjustment = True
                st.error(f"❌ 速度梯度 G1 不在正常范围内: {t1_results['G1']:.2f} s⁻¹ (正常范围: {g1_min}-{g1_max} s⁻¹)")
                st.info("💡 系统已尝试自动调整，如需进一步优化可手动调整参数")
            else:
                st.session_state.show_adjustment = False
                st.success(f"✅ 速度梯度 G1 在正常范围内 ({g1_min}-{g1_max} s⁻¹)")

            # 检查导流筒覆盖面积比值
            if not t1_results['Y_guide_in_range']:
                st.warning(f"⚠️ 导流筒覆盖面积比值不在建议范围内: {t1_results['Y_guide']:.3f} (建议: 0.15-0.20)")

            # 检查流速校核
            if not t1_results['velocity_check_ok']:
                st.warning(f"⚠️ 各部位流速差异较大: {t1_results['velocity_diff']:.3f} m/s，建议优化设计")
        elif reactor_type == "T3反应池":
            # T3需要检查上下层速度梯度
            g_lower_min, g_lower_max = t1_results['G_lower_range']
            g_upper_min, g_upper_max = t1_results['G_upper_range']

            g_lower_ok = t1_results['G_lower_in_range']
            g_upper_ok = t1_results['G_upper_in_range']

            if not g_lower_ok or not g_upper_ok:
                st.session_state.show_adjustment = True
                if not g_lower_ok:
                    st.error(
                        f"❌ 下层速度梯度 G_lower 不在正常范围内: {t1_results['G_lower']:.2f} s⁻¹ (正常范围: {g_lower_min}-{g_lower_max} s⁻¹)")
                if not g_upper_ok:
                    st.error(
                        f"❌ 上层速度梯度 G_upper 不在正常范围内: {t1_results['G_upper']:.2f} s⁻¹ (正常范围: {g_upper_min}-{g_upper_max} s⁻¹)")
                st.info("💡 系统已尝试自动调整，如需进一步优化可手动调整参数")
            else:
                st.session_state.show_adjustment = False
                st.success(f"✅ 上下层速度梯度均在正常范围内")
        else:
            # T1T2反应池的速度梯度检查
            g1_min, g1_max = t1_results['G1_range']
            if not t1_results['G1_in_range']:
                st.session_state.show_adjustment = True
                st.error(f"❌ 速度梯度 G1 不在正常范围内: {t1_results['G1']:.2f} s⁻¹ (正常范围: {g1_min}-{g1_max} s⁻¹)")
                st.info("💡 系统已尝试自动调整，如需进一步优化可手动调整参数")
            else:
                st.session_state.show_adjustment = False
                st.success(f"✅ 速度梯度 G1 在正常范围内 ({g1_min}-{g1_max} s⁻¹)")
        # 显示计算结果
        display_results()

    # 显示调整界面（如果需要）
    if st.session_state.calculation_completed and st.session_state.show_adjustment:
        st.header("🔄 手动参数调整")
        if st.session_state.reactor_type == "沉淀池":
            st.header("🔄 沉淀池参数调整")
            st.info("沉淀池参数调整功能待开发")

        elif st.session_state.reactor_type == "单级絮凝池":
            g1_min, g1_max = st.session_state.t1_results['G1_range']
            st.info(f"请调整以下参数以使速度梯度 G1 进入正常范围 ({g1_min}-{g1_max} s⁻¹)")

            col1, col2 = st.columns(2)
            with col1:
                current_d1 = st.session_state.t1_results['d1']
                adjusted_d1 = st.number_input("搅拌直径 d1 (m)", min_value=0.1, max_value=10.0,
                                              value=current_d1, step=0.1)

            with col2:
                current_v1 = st.session_state.t1_results['v1']
                adjusted_v1 = st.number_input("搅拌桨叶外缘线速度 v1 (m/s)", min_value=1.0, max_value=10.0,
                                              value=current_v1, step=0.1)
        elif st.session_state.reactor_type == "T3反应池":
            g_lower_min, g_lower_max = st.session_state.t1_results['G_lower_range']
            g_upper_min, g_upper_max = st.session_state.t1_results['G_upper_range']
            st.info(f"请调整以下参数以使速度梯度进入正常范围")
            st.info(f"下层G: {g_lower_min}-{g_lower_max} s⁻¹, 上层G: {g_upper_min}-{g_upper_max} s⁻¹")

            col1, col2 = st.columns(2)
            with col1:
                # 获取当前值作为默认值
                current_d_lower = st.session_state.t1_results['d_lower']
                adjusted_d_lower = st.number_input("下层搅拌直径 d_lower (m)",
                                                   min_value=0.1, max_value=10.0,
                                                   value=current_d_lower, step=0.1)

            with col2:
                current_v_lower = st.session_state.t1_results['v_lower']
                adjusted_v_lower = st.number_input("下层桨叶外缘线速度 v_lower (m/s)",
                                                   min_value=1.0, max_value=10.0,
                                                   value=current_v_lower, step=0.1)
        else:
            # T1T2反应池的调整界面
            g1_min, g1_max = st.session_state.t1_results['G1_range']
            st.info(f"请调整以下参数以使速度梯度 G1 进入正常范围 ({g1_min}-{g1_max} s⁻¹)")

            col1, col2 = st.columns(2)
            with col1:
                current_d1 = st.session_state.t1_results['d1']
                adjusted_d1 = st.number_input("搅拌直径 d1 (m)", min_value=0.1, max_value=10.0,
                                              value=current_d1, step=0.1)

            with col2:
                current_v1 = st.session_state.t1_results['v1']
                adjusted_v1 = st.number_input("搅拌桨叶外缘线速度 v1 (m/s)", min_value=1.0, max_value=10.0,
                                              value=current_v1, step=0.1)

        if st.button("重新计算", type="primary"):
            # 使用调整后的参数重新计算
            if st.session_state.reactor_type == "单级絮凝池":
                adjusted_results = calculator.calculate_single_stage_flocculation(
                    ss_in, st.session_state.flow_rate, construction_type,
                    st.session_state.t1_results.get('d_inlet'),
                    st.session_state.t1_results.get('inlet_type', '泵入进水'),
                    st.session_state.q_max
                )
            elif st.session_state.reactor_type == "T1反应池":
                if st.session_state.calculation_mode == "正向计算":
                    adjusted_results = calculator.calculate_t1_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape,
                        d1=adjusted_d1, v1=adjusted_v1, calculation_mode=st.session_state.calculation_mode
                    )
                else:
                    adjusted_results = calculator.calculate_t1_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape,
                        st.session_state.l, st.session_state.w, st.session_state.t1_results['h2'],
                        d1=adjusted_d1, v1=adjusted_v1, calculation_mode=st.session_state.calculation_mode
                    )
            elif st.session_state.reactor_type == "T2反应池":
                if st.session_state.calculation_mode == "正向计算":
                    adjusted_results = calculator.calculate_t2_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape,
                        d1=adjusted_d1, v1=adjusted_v1, calculation_mode=st.session_state.calculation_mode
                    )
                else:
                    adjusted_results = calculator.calculate_t2_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape,
                        st.session_state.l, st.session_state.w, st.session_state.t1_results['h2'],
                        d1=adjusted_d1, v1=adjusted_v1, calculation_mode=st.session_state.calculation_mode
                    )
            else:  # T3反应池
                if st.session_state.calculation_mode == "正向计算":
                    adjusted_results = calculator.calculate_t3_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape,
                        d_lower=adjusted_d_lower, v_lower=adjusted_v_lower,
                        calculation_mode=st.session_state.calculation_mode
                    )
                else:
                    adjusted_results = calculator.calculate_t3_parameters(
                        ss_in, st.session_state.flow_rate, construction_type, st.session_state.pool_shape,
                        st.session_state.l, st.session_state.w, st.session_state.t1_results['h2'],
                        d_lower=adjusted_d_lower, v_lower=adjusted_v_lower,
                        calculation_mode=st.session_state.calculation_mode
                    )
            # 这里简化处理，实际应该用调整后的d1和v1重新计算
            # 更新会话状态
            st.session_state.t1_results = adjusted_results

            # 显示自动调整日志
            if adjusted_results.get('adjustment_log'):
                st.header("🔄 自动调整记录")
                for log in adjusted_results['adjustment_log']:
                    st.info(log)

            # 检查调整后的速度梯度
            if st.session_state.reactor_type == "单级絮凝池":
                g1_min, g1_max = adjusted_results['G1_range']
                if adjusted_results['G1_in_range']:
                    st.session_state.show_adjustment = False
                    st.success(f"✅ 调整成功！速度梯度 G1 现在在正常范围内: {adjusted_results['G1']:.2f} s⁻¹")
                else:
                    st.error(f"❌ 速度梯度 G1 仍然不在正常范围内: {adjusted_results['G1']:.2f} s⁻¹")
            elif st.session_state.reactor_type == "T3反应池":
                g_lower_ok = adjusted_results['G_lower_in_range']
                g_upper_ok = adjusted_results['G_upper_in_range']
                if g_lower_ok and g_upper_ok:
                    st.session_state.show_adjustment = False
                    st.success(f"✅ 调整成功！上下层速度梯度现在均在正常范围内")
                else:
                    if not g_lower_ok:
                        st.error(f"❌ 下层速度梯度 G_lower 仍然不在正常范围内: {adjusted_results['G_lower']:.2f} s⁻¹")
                    if not g_upper_ok:
                        st.error(f"❌ 上层速度梯度 G_upper 仍然不在正常范围内: {adjusted_results['G_upper']:.2f} s⁻¹")
            else:
                g1_min, g1_max = adjusted_results['G1_range']
                if adjusted_results['G1_in_range']:
                    st.session_state.show_adjustment = False
                    st.success(f"✅ 调整成功！速度梯度 G1 现在在正常范围内: {adjusted_results['G1']:.2f} s⁻¹")
                else:
                    st.error(f"❌ 速度梯度 G1 仍然不在正常范围内: {adjusted_results['G1']:.2f} s⁻¹")
            # 显示调整后的结果
            display_results()


def display_sedimentation_results(results, flow_rate, calculation_mode):
    """显示沉淀池计算结果"""
    st.subheader("沉淀池主要计算结果")

    # 基本信息
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**基本参数**")
        st.metric("小时处理量", f"{flow_rate / 24:.2f} m³/h")
        st.metric("沉淀池面积", f"{results['A_sedimentation']:.2f} m²")
        st.metric("池体长度", f"{results['L_pool']:.3f} m")
        st.metric("池体宽度", f"{results['B_pool']:.3f} m")
        if 'n_tube_design' in results:
            st.metric("设计斜管利用率", f"{results['n_tube_design'] * 100:.1f}%")

    with col2:
        st.write("**斜管参数**")
        st.metric("斜管长度", f"{results.get('l_tube', 'N/A')} m")
        st.metric("斜管高度", f"{results.get('h3_sedimentation', 'N/A'):.3f} m")
        st.metric("实际斜管利用率", f"{results['n_tube_actual'] * 100:.1f}%")
        if calculation_mode == "反向计算":
            st.metric("表面水力负荷", f"{results['q_sedimentation']:.2f} m³/(m²·h)")

        st.write("**布水区参数**")
        st.metric("布水区宽度", f"{results['b_water_distribution']:.3f} m")
        st.metric("布水流速", f"{results['v_water_distribution']:.3f} m/s")

    with col3:
        st.write("**池体高度参数**")
        st.metric("总高度", f"{results['h_total_sedimentation']:.3f} m")
        st.metric("清水区高度", f"{results['h2_sedimentation']:.3f} m")
        st.metric("缓冲区高度", f"{results['h4_sedimentation']:.3f} m")
        st.metric("底坡高度", f"{results['h5_sedimentation']:.3f} m")

    # 高度分解
    st.subheader("池体高度分解")
    height_data = {
        '组成部分': ['超高 h1', '清水区 h2', '斜管区 h3', '缓冲区 h4', '底坡 h5', '泥斗 h6', '总高'],
        '高度(m)': [
            results['h1_sedimentation'],
            results['h2_sedimentation'],
            results.get('h3_sedimentation', 0),
            results['h4_sedimentation'],
            results['h5_sedimentation'],
            results['h6_sedimentation'],
            results['h_total_sedimentation']
        ]
    }
    height_df = pd.DataFrame(height_data)
    st.dataframe(height_df, use_container_width=True, hide_index=True)

    # 泥斗设计
    st.subheader("泥斗设计参数")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**泥斗尺寸**")
        st.write(f"泥斗上部直径: {results['D_sludge']:.3f} m")
        st.write(f"泥斗下部直径: {results['d_sludge']:.3f} m")
        st.write(f"泥斗高度: {results['h6_sedimentation']:.3f} m")
        st.write(f"泥斗角度: {results['a_hopper']}°")
        st.write(f"底坡角度: {results['a_slope']}°")

    with col2:
        st.write("**过水板复核**")
        st.write(f"过水板高度: {results['h_water_board']:.3f} m")
        st.write(f"过水流速: {results['v_water_board']:.3f} m/s")
        if results['v_water_board_in_range']:
            st.success("✅ 过水流速在正常范围内 (0.02-0.03 m/s)")
        else:
            st.warning("⚠️ 过水流速不在建议范围内")

    # 出水系统设计
    st.subheader("出水系统设计")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**三角堰设计**")
        st.write(f"三角堰数量: {results['n_triangle_weir']}")
        st.write(f"布置方式: {results['layout_type']}")
        st.write(f"堰口总数: {results['y_weir_openings']}")
        st.write(f"堰口宽度: {results['b_triangle_weir']:.3f} m")
        st.write(f"堰上水头: {results['h_y_triangle_weir']:.4f} m")
        st.write(f"实际堰上负荷: {results['q_actual_weir_load']:.2f} L/(s·m)")
        if results['q_weir_load_check']:
            st.success("✅ 堰上负荷满足要求 (≤5.8 L/(s·m))")
        else:
            st.warning("⚠️ 堰上负荷超出建议范围")

    with col2:
        st.write("**集水槽设计**")
        st.write(f"集水槽数量: {results['n_collection_tank']}")
        st.write(f"集水槽宽度: {results['b_collection_tank']:.3f} m")
        st.write(f"集水槽总高度: {results['h_total_collection']:.3f} m")
        st.write(f"临界水深: {results['h_k']:.3f} m")
        st.write(f"起端水深: {results['h_start']:.3f} m")
        st.write(f"水头损失: {results['delta_h_collection']:.3f} m")
        st.write(f"集水堰总高: {results['h_collection_weir']:.3f} m")

    # 刮泥机设计
    st.subheader("刮泥机设计")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**污泥参数**")
        st.write(f"干污泥量: {results['Q_sludge_dry']:.6f} m³/h")
        st.write(f"积泥量(含水98%): {results['Q_sludge_accumulated']:.6f} m³/h")
        st.write(f"刮泥机线速度: {results['v_scraper']} m/min")
        st.write(f"刮泥机转速: {results['r_scraper']:.3f} r/min")

    with col2:
        st.write("**功率计算**")
        st.write(f"刮泥阻力: {results['P_scraper']:.2f} N")
        st.write(f"计算功率: {results['N_scraper']:.4f} kW")
        st.write(f"电机选型功率: {results['selected_scraper_power']} kW")
        st.info("💡 刮泥机电机根据处理量选型：>5000m³/d用0.37kW，≤5000m³/d用0.25kW")

    # 结果汇总表格
    st.subheader("结果汇总")
    summary_data = {
        '参数': [
            '沉淀池类型', '计算模式', '池体尺寸(m)', '沉淀池面积(m²)',
            '斜管利用率(%)', '表面负荷(m³/(m²·h))', '布水区宽度(m)', '布水流速(m/s)',
            '池体总高(m)', '清水区高度(m)', '缓冲区高度(m)', '底坡高度(m)',
            '泥斗高度(m)', '过水板高度(m)', '过水流速(m/s)',
            '三角堰数量', '集水槽数量', '堰口总数', '实际堰上负荷(L/(s·m))',
            '刮泥机功率(kW)', '干污泥量(m³/h)', '积泥量(m³/h)'
        ],
        '数值': [
            '沉淀池', calculation_mode, f"{results['L_pool']:.2f}×{results['B_pool']:.2f}",
            f"{results['A_sedimentation']:.2f}", f"{results['n_tube_actual'] * 100:.1f}",
            f"{20 if calculation_mode == '正向计算' else results.get('q_sedimentation', 20):.2f}",
            f"{results['b_water_distribution']:.3f}", f"{results['v_water_distribution']:.3f}",
            f"{results['h_total_sedimentation']:.3f}", f"{results['h2_sedimentation']:.3f}",
            f"{results['h4_sedimentation']:.3f}", f"{results['h5_sedimentation']:.3f}",
            f"{results['h6_sedimentation']:.3f}", f"{results['h_water_board']:.3f}",
            f"{results['v_water_board']:.3f}", f"{results['n_triangle_weir']}",
            f"{results['n_collection_tank']}", f"{results['y_weir_openings']}",
            f"{results['q_actual_weir_load']:.2f}", f"{results['selected_scraper_power']}",
            f"{results['Q_sludge_dry']:.6f}", f"{results['Q_sludge_accumulated']:.6f}"
        ]
    }

    df = pd.DataFrame(summary_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 显示调整日志
    if results.get('adjustment_log'):
        st.header("🔄 自动调整记录")
        for log in results['adjustment_log']:
            st.info(log)

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

    if reactor_type == "沉淀池":
        display_sedimentation_results(
            t1_results,
            st.session_state.flow_rate,
            st.session_state.calculation_mode
        )
        return
    elif reactor_type == "单级絮凝池":
        display_single_stage_results(t1_results, flow_rate, flow_display_name, q0, q_max, flow_selection)
    else:
        # 原有的T1, T2, T3结果显示逻辑
        # 为简洁起见，这里省略具体实现
        st.subheader(f"{reactor_type}主要计算结果")

        if reactor_type == "T3反应池":
            # T3反应池的特殊显示格式
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
                st.metric("下层搅拌直径", f"{t1_results['d_lower']:.3f} m")
                st.metric("上层搅拌直径", f"{t1_results['d_upper']:.3f} m")

            with col3:
                st.write("**搅拌参数**")
                st.metric("下层桨叶线速度", f"{t1_results['v_lower']:.2f} m/s")
                st.metric("上层桨叶线速度", f"{t1_results['v_upper']:.2f} m/s")
                st.metric("搅拌转速", f"{t1_results['n_lower']:.2f} r/min")
                st.metric("总电动机功率", f"{t1_results['N_total']:.4f} kW")
                st.metric("总电动机选型功率", f"{t1_results['selected_motor_power_total']} kW")

            # 显示详细结果
            st.subheader("详细计算结果")

            col1, col2 = st.columns(2)

            with col1:
                st.write("**下层搅拌系统参数**")
                st.write(f"下层搅拌功率: {t1_results['N_lower']:.4f} kW")
                st.write(f"下层电动机功率: {t1_results['Na_lower']:.4f} kW")
                st.write(f"下层电动机选型功率: {t1_results['selected_motor_power_lower']} kW")
                st.write(f"下层桨叶宽度: {t1_results['b_lower']:.3f} m")
                st.write(f"下层速度梯度: {t1_results['G_lower']:.2f} s⁻¹")

                # 下层速度梯度检查
                g_lower_min, g_lower_max = t1_results['G_lower_range']
                if t1_results['G_lower_in_range']:
                    st.success(f"✅ 下层速度梯度在正常范围内 ({g_lower_min}-{g_lower_max} s⁻¹)")
                else:
                    st.error(f"❌ 下层速度梯度不在正常范围内: {t1_results['G_lower']:.2f} s⁻¹")

                st.write("**上层搅拌系统参数**")
                st.write(f"上层搅拌功率: {t1_results['N_upper']:.4f} kW")
                st.write(f"上层电动机功率: {t1_results['Na_upper']:.4f} kW")
                st.write(f"上层电动机选型功率: {t1_results['selected_motor_power_upper']} kW")
                st.write(f"上层桨叶宽度: {t1_results['b_upper']:.3f} m")
                st.write(f"上层速度梯度: {t1_results['G_upper']:.2f} s⁻¹")

                # 上层速度梯度检查
                g_upper_min, g_upper_max = t1_results['G_upper_range']
                if t1_results['G_upper_in_range']:
                    st.success(f"✅ 上层速度梯度在正常范围内 ({g_upper_min}-{g_upper_max} s⁻¹)")
                else:
                    st.error(f"❌ 上层速度梯度不在正常范围内: {t1_results['G_upper']:.2f} s⁻¹")

            with col2:
                st.write("**复核参数**")
                st.write(f"下层 S1/S 比值: {t1_results['S1_S_ratio_lower']:.4f}")
                if t1_results['S1_S_in_range_lower']:
                    st.success("✅ 下层 S1/S 比值满足要求 (< 0.2)")
                else:
                    st.error(f"❌ 下层 S1/S 比值不小于 0.2: {t1_results['S1_S_ratio_lower']:.4f}")

                st.write(f"上层 S1/S 比值: {t1_results['S1_S_ratio_upper']:.4f}")
                if t1_results['S1_S_in_range_upper']:
                    st.success("✅ 上层 S1/S 比值满足要求 (< 0.12)")
                else:
                    st.error(f"❌ 上层 S1/S 比值不小于 0.12: {t1_results['S1_S_ratio_upper']:.4f}")

                st.write(f"h2/D 比值: {t1_results['h2'] / t1_results['D']:.3f}")

                # 桨叶间距复核
                st.write("**桨叶间距复核**")
                st.write(f"下层距池底距离: {t1_results['l1']:.3f} m")
                st.write(f"上下层间距: {t1_results['l2']:.3f} m")
                st.write(f"上层距水面距离: {t1_results['distance_to_surface']:.3f} m")

                dist_min, dist_max = t1_results['distance_surface_range']
                if t1_results['distance_surface_in_range']:
                    st.success(f"✅ 上层距水面距离在正常范围内 ({dist_min:.3f}-{dist_max:.3f} m)")
                else:
                    st.warning(
                        f"⚠️ 上层距水面距离不在建议范围内: {t1_results['distance_to_surface']:.3f} m (建议: {dist_min:.3f}-{dist_max:.3f} m)")

                # 反向计算特别提示
                if calculation_mode == "反向计算":
                    st.info(f"📐 反向计算：根据输入的池体尺寸，反推得到水力停留时间 t1 = {t1_results['t1']:.2f} s")

        else:
            # T1T2反应池的显示格式（原有逻辑）
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

        if reactor_type == "T3反应池":
            summary_data = {
                '参数': [
                    '反应池类型', '计算模式', '流量选择',
                    '单套设备处理量 Q0 (m³/d)', '单套设备最大处理量 Qmax (m³/d)', '计算使用流量 (m³/d)',
                    '水力停留时间 t1 (s)', '反应池体积 V1 (m³)', '池体当量直径 D (m)',
                    '池体长度 l (m)', '池体宽度 w (m)', '有效高度 h2 (m)', '池体超高 h1 (m)',
                    '池体总高 h总 (m)', '下层桨叶线速度 (m/s)', '上层桨叶线速度 (m/s)',
                    '下层搅拌直径 (m)', '上层搅拌直径 (m)', '搅拌转速 (r/min)',
                    '下层搅拌功率 (kW)', '上层搅拌功率 (kW)', '总电动机功率 (kW)',
                    '总电动机选型功率 (kW)', '下层速度梯度 (s⁻¹)', '上层速度梯度 (s⁻¹)'
                ],
                '数值': [
                    reactor_type, calculation_mode, flow_selection,
                    f"{q0:.2f}", f"{q_max:.2f}", f"{flow_rate:.2f}",
                    f"{t1_results['t1']:.2f}", f"{t1_results['V1']:.3f}", f"{t1_results['D']:.3f}",
                    f"{t1_results['l']:.3f}" if t1_results['l'] else ("N/A" if pool_shape == "圆形" else f"{l:.3f}"),
                    f"{t1_results['w']:.3f}" if t1_results['w'] else ("N/A" if pool_shape == "圆形" else f"{w:.3f}"),
                    f"{t1_results['h2']:.3f}", f"{t1_results['h1']:.3f}",
                    f"{t1_results['h_total']:.3f}", f"{t1_results['v_lower']:.2f}",
                    f"{t1_results['v_upper']:.2f}", f"{t1_results['d_lower']:.3f}",
                    f"{t1_results['d_upper']:.3f}", f"{t1_results['n_lower']:.2f}",
                    f"{t1_results['N_lower']:.4f}", f"{t1_results['N_upper']:.4f}",
                    f"{t1_results['N_total']:.4f}", f"{t1_results['selected_motor_power_total']}",
                    f"{t1_results['G_lower']:.2f}", f"{t1_results['G_upper']:.2f}"
                ]
            }
        else:
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


def display_single_stage_results(t1_results, flow_rate, flow_display_name, q0, q_max, flow_selection):
    """显示单级絮凝池计算结果"""
    st.subheader("单级絮凝池主要计算结果")

    # 基本信息
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**基本参数**")
        st.metric("水力停留时间 t1", f"{t1_results['t1']:.2f} s")
        st.metric("反应池体积 V1", f"{t1_results['V1']:.3f} m³")
        st.metric("池体当量直径 D", f"{t1_results['D']:.3f} m")
        st.metric("池体长度 l", f"{t1_results['l']:.3f} m")
        st.metric("池体宽度 w", f"{t1_results['w']:.3f} m")

    with col2:
        st.write("**尺寸参数**")
        st.metric("有效高度 h2", f"{t1_results['h2']:.3f} m")
        st.metric("池体超高 h1", f"{t1_results['h1']:.3f} m")
        st.metric("池体总高 h总", f"{t1_results['h_total']:.3f} m")
        st.metric("搅拌直径 d1", f"{t1_results['d1']:.3f} m")
        st.metric("设计流量 Qmax1", f"{t1_results['Q_max1']:.6f} m³/s")

    with col3:
        st.write("**搅拌参数**")
        st.metric("桨叶线速度 v1", f"{t1_results['v1']:.2f} m/s")
        st.metric("搅拌转速 n1", f"{t1_results['n1']:.2f} r/min")
        st.metric("搅拌功率 N1", f"{t1_results['N1']:.4f} kW")
        st.metric("电动机功率 Na1", f"{t1_results['Na1']:.4f} kW")
        st.metric("电动机选型功率", f"{t1_results['selected_motor_power']} kW")

    # 折流混合区设计结果
    st.subheader("折流混合区设计结果")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**进水口参数**")
        st.write(f"进水类型: {t1_results['inlet_type']}")
        st.write(f"进水口口径: {t1_results['d_inlet']} mm")
        st.write(f"进水口面积: {t1_results['S_inlet']:.6f} m²")
        st.write(f"进水流速: {t1_results['v_inlet']:.3f} m/s")

        st.write("**折流区基本参数**")
        st.write(f"折流区长度: {t1_results['l_baffle']:.3f} m")
        st.write(f"折流区宽度: {t1_results['b_baffle']:.3f} m")
        st.write(f"折流区有效高度: {t1_results['h2_baffle']:.3f} m")
        st.write(f"折流区停留时间: {t1_results['t_baffle']} s")

    with col2:
        st.write("**折流板参数**")
        st.write(f"折流板数量: {t1_results['n_baffle']} 层")
        st.write(f"折流板间距: {t1_results['b1_baffle']:.3f} m")
        st.write(f"底层距底高度: {t1_results['h_baffle_bottom']:.3f} m")
        st.write(f"顶部距水面高度: {t1_results['h_baffle_top']:.3f} m")

        st.write("**扰流板参数**")
        st.write(f"扰流板高度: {t1_results['h_disturb']:.3f} m")
        st.write(f"下部扰流板数量: {t1_results['n_disturb']} 个")
        st.write(f"顶部扰流板数量: {t1_results['n_disturb_top']} 个")
        st.write(f"扰流板总数: {t1_results['n_disturb_total']} 个")

    # 导流筒设计结果
    st.subheader("导流筒设计结果")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**导流筒基本参数**")
        st.write(f"导流筒直径: {t1_results['D_d']:.3f} m")
        st.write(f"导流筒面积: {t1_results['S_d']:.4f} m²")
        st.write(f"池体面积: {t1_results['S_pool']:.4f} m²")
        st.write(f"覆盖面积比值: {t1_results['Y_guide']:.3f}")
        if t1_results['Y_guide_in_range']:
            st.success("✅ 导流筒覆盖面积比值在正常范围内 (0.15-0.20)")
        else:
            st.warning("⚠️ 导流筒覆盖面积比值不在建议范围内")

        st.write(f"絮凝回流比: {t1_results['r_guide']:.2f}")
        st.write(f"导流筒总高度: {t1_results['h_guide_total']:.3f} m")
        st.write(f"喇叭口高度: {t1_results['h_horn']:.3f} m")

    with col2:
        st.write("**底部导流板参数**")
        st.write(f"导流板高度: {t1_results['h_guide_plate']:.3f} m")
        st.write(f"导流板宽度: {t1_results['b_guide_plate']:.3f} m")
        st.write(f"导流板数量: {t1_results['n_guide_plate']} 块")

        st.write("**流速校核**")
        st.write(f"导流筒内流速: {t1_results['v1_guide']:.3f} m/s")
        st.write(f"导流筒上缘流速: {t1_results['v2_upper']:.3f} m/s")
        st.write(f"喇叭口以上流速: {t1_results['v3_above_horn']:.3f} m/s")
        st.write(f"喇叭口处流速: {t1_results['v4_horn']:.3f} m/s")
        st.write(f"喇叭口以下流速: {t1_results['v5_below']:.3f} m/s")
        st.write(f"最大流速差: {t1_results['velocity_diff']:.3f} m/s")
        if t1_results['velocity_check_ok']:
            st.success("✅ 各部位流速差异较小，环流效果良好")
        else:
            st.warning("⚠️ 各部位流速差异较大，建议优化设计")

    # 复核参数
    st.subheader("复核参数")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**搅拌系统复核**")
        st.write(f"S1/S 比值: {t1_results['S1_S_ratio']:.4f}")
        if t1_results['S1_S_in_range']:
            st.success("✅ S1/S 比值满足要求 (< 0.25)")
        else:
            st.error(f"❌ S1/S 比值不小于 0.25: {t1_results['S1_S_ratio']:.4f}")

        st.write(f"搅拌层数: {t1_results['e']}")
        st.write(f"桨叶宽度: {t1_results['b']:.3f} m")
        st.write(f"速度梯度 G1: {t1_results['G1']:.2f} s⁻¹")

        g1_min, g1_max = t1_results['G1_range']
        if t1_results['G1_in_range']:
            st.success(f"✅ 速度梯度 G1 在正常范围内 ({g1_min}-{g1_max} s⁻¹)")
        else:
            st.error(f"❌ 速度梯度 G1 不在正常范围内: {t1_results['G1']:.2f} s⁻¹")

    with col2:
        st.write("**几何尺寸复核**")
        st.write(f"h2/D 比值: {t1_results['h2'] / t1_results['D']:.3f}")
        st.write(f"桨叶间距: {t1_results['l1_single']:.3f} m")

        # 新增：桨叶间距复核显示
        st.write("**桨叶间距复核**")
        st.write(f"下层距池底距离: {t1_results['l1']:.3f} m")
        st.write(f"桨叶间距: {t1_results['l2']:.3f} m")
        st.write(f"上层距水面距离: {t1_results['distance_to_surface']:.3f} m")

        dist_min, dist_max = t1_results['distance_surface_range']
        if t1_results['distance_surface_in_range']:
            st.success(f"✅ 上层距水面距离在正常范围内 ({dist_min:.3f}-{dist_max:.3f} m)")
        else:
            st.warning(
                f"⚠️ 上层距水面距离不在建议范围内: {t1_results['distance_to_surface']:.3f} m (建议: {dist_min:.3f}-{dist_max:.3f} m)")

    # 结果汇总表格
    st.subheader("结果汇总")
    summary_data = {
        '参数': [
            '反应池类型', '计算模式', '流量选择', '进水类型',
            '单套设备处理量 Q0 (m³/d)', '单套设备最大处理量 Qmax (m³/d)', '计算使用流量 (m³/d)',
            '水力停留时间 t1 (s)', '反应池体积 V1 (m³)', '池体当量直径 D (m)',
            '池体长度 l (m)', '池体宽度 w (m)', '有效高度 h2 (m)', '池体超高 h1 (m)',
            '池体总高 h总 (m)', '搅拌桨叶线速度 v1 (m/s)', '搅拌转速 n1 (r/min)',
            '搅拌直径 d1 (m)', '搅拌功率 N1 (kW)', '电动机功率 Na1 (kW)',
            '电动机选型功率 (kW)', '速度梯度 G1 (s⁻¹)', '导流筒覆盖面积比值',
            '絮凝回流比', '最大流速差 (m/s)'
        ],
        '数值': [
            '单级絮凝池', '正向计算', flow_selection, t1_results['inlet_type'],
            f"{q0:.2f}", f"{q_max:.2f}", f"{flow_rate:.2f}",
            f"{t1_results['t1']:.2f}", f"{t1_results['V1']:.3f}", f"{t1_results['D']:.3f}",
            f"{t1_results['l']:.3f}", f"{t1_results['w']:.3f}", f"{t1_results['h2']:.3f}",
            f"{t1_results['h1']:.3f}", f"{t1_results['h_total']:.3f}", f"{t1_results['v1']:.2f}",
            f"{t1_results['n1']:.2f}", f"{t1_results['d1']:.3f}", f"{t1_results['N1']:.4f}",
            f"{t1_results['Na1']:.4f}", f"{t1_results['selected_motor_power']}",
            f"{t1_results['G1']:.2f}", f"{t1_results['Y_guide']:.3f}",
            f"{t1_results['r_guide']:.2f}", f"{t1_results['velocity_diff']:.3f}"
        ]
    }

    df = pd.DataFrame(summary_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()