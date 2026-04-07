/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";

const CATEGORY_COLORS = ["#ff8a00", "#ffac2f", "#ffc768", "#ffdc9a", "#ffe9c6", "#f5be7f"];

export class MagentoDashboard extends Component {
    static template = "sdlc_magento_connector.MagentoDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");

        const context = this.props.action?.context || {};
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            instanceId: context.default_instance_id || false,
            days: Number(context.dashboard_days || 8),
        });

        this.refreshMs = 30000;
        this.refreshTimer = null;
        this.actionRoot = null;

        onWillStart(async () => {
            await this._loadData({ showLoader: true });
            this._startAutoRefresh();
        });
        onMounted(() => {
            this.actionRoot = this.el?.closest?.(".o_action") || null;
            if (this.actionRoot) {
                this.actionRoot.classList.add("o_magento_dash_action");
                this.actionRoot.style.height = "100%";
                this.actionRoot.style.overflowY = "auto";
                this.actionRoot.style.overflowX = "hidden";
            }
            if (this.el) {
                this.el.style.minHeight = "100%";
            }
        });
        onWillUnmount(() => {
            this._stopAutoRefresh();
            if (this.actionRoot) {
                this.actionRoot.classList.remove("o_magento_dash_action");
                this.actionRoot.style.overflowY = "";
                this.actionRoot.style.overflowX = "";
                this.actionRoot.style.height = "";
                this.actionRoot = null;
            }
        });
    }

    _startAutoRefresh() {
        this._stopAutoRefresh();
        this.refreshTimer = setInterval(() => {
            this._loadData({ showLoader: false });
        }, this.refreshMs);
    }

    _stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    async _loadData({ showLoader = false } = {}) {
        if (showLoader) {
            this.state.loading = true;
        }
        try {
            const payload = await this.orm.call("magento.instance", "get_dashboard_data", [
                this.state.instanceId || false,
                this.state.days || 8,
            ]);
            this.state.data = payload || {};
            this.state.instanceId = payload?.selected_instance_id || false;
            this.state.error = "";
        } catch (error) {
            this.state.error = error?.message || "Failed to load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async onRefreshClick() {
        await this._loadData({ showLoader: false });
    }

    async onInstanceChange(ev) {
        const value = ev.target.value;
        this.state.instanceId = value ? parseInt(value, 10) : false;
        await this._loadData({ showLoader: true });
    }

    async onPeriodChange(ev) {
        const value = parseInt(ev.target.value, 10);
        this.state.days = Number.isFinite(value) ? value : 8;
        await this._loadData({ showLoader: true });
    }

    get hasData() {
        return !!this.state.data;
    }

    get data() {
        return this.state.data || {};
    }

    get instances() {
        return this.data.instances || [];
    }

    get kpis() {
        return this.data.kpis || {};
    }

    get salesSeries() {
        return this.data.sales_series || [];
    }

    get monthlyTarget() {
        return this.data.monthly_target || {};
    }

    get topCategories() {
        return this.data.top_categories || [];
    }

    get topCategoriesStyled() {
        return this.topCategories.map((row, index) => ({
            ...row,
            color: this.categoryColor(index),
        }));
    }

    get totalCategoryValue() {
        return this.topCategories.reduce((acc, item) => acc + Number(item.value || 0), 0);
    }

    get topCountries() {
        return this.data.top_countries || [];
    }

    get orderStatus() {
        return this.data.order_status || [];
    }

    get syncHealth() {
        return this.data.sync_health || {};
    }

    get chartLabels() {
        return this.salesSeries.map((point) => this.formatDay(point.date));
    }

    formatNumber(value) {
        return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(Number(value || 0));
    }

    formatCurrency(value) {
        const currencyCode = this.data.currency || "USD";
        return new Intl.NumberFormat(undefined, {
            style: "currency",
            currency: currencyCode,
            maximumFractionDigits: 0,
        }).format(Number(value || 0));
    }

    formatPercent(value) {
        const numeric = Number(value || 0);
        const prefix = numeric > 0 ? "+" : "";
        return `${prefix}${numeric.toFixed(2)}%`;
    }

    formatDateTime(value) {
        if (!value) {
            return "Never";
        }
        const normalized = String(value).trim().replace(" ", "T");
        const hasTimezone = /([zZ]|[+\-]\d{2}:?\d{2})$/.test(normalized);
        const parsed = new Date(hasTimezone ? normalized : `${normalized}Z`);
        if (Number.isNaN(parsed.getTime())) {
            return value;
        }
        return new Intl.DateTimeFormat("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: true,
            timeZone: "Asia/Kolkata",
            timeZoneName: "short",
        }).format(parsed);
    }

    formatDay(value) {
        if (!value) {
            return "";
        }
        const parsed = new Date(String(value));
        if (Number.isNaN(parsed.getTime())) {
            return value;
        }
        return new Intl.DateTimeFormat("en-IN", {
            month: "short",
            day: "numeric",
            timeZone: "Asia/Kolkata",
        }).format(parsed);
    }

    deltaClass(value) {
        return Number(value || 0) >= 0 ? "o_magento_delta_up" : "o_magento_delta_down";
    }

    barWidthStyle(value) {
        const width = Math.max(6, Math.min(100, Number(value || 0)));
        return `width: ${width}%;`;
    }

    categoryColor(index) {
        return CATEGORY_COLORS[index % CATEGORY_COLORS.length];
    }

    get categoryDonutStyle() {
        if (!this.topCategoriesStyled.length) {
            return "background: conic-gradient(#f3e8d5 0deg 360deg);";
        }
        const total =
            this.topCategoriesStyled.reduce((sum, item) => sum + Number(item.value || 0), 0) || 1;
        let start = 0;
        const ranges = this.topCategoriesStyled.map((item) => {
            const delta = (Number(item.value || 0) / total) * 360;
            const end = start + delta;
            const token = `${item.color} ${start.toFixed(2)}deg ${end.toFixed(2)}deg`;
            start = end;
            return token;
        });
        return `background: conic-gradient(${ranges.join(", ")});`;
    }

    _seriesPoints(metricName, width = 560, height = 220, padding = 20) {
        const series = this.salesSeries;
        if (!series.length) {
            return [];
        }
        const values = series.map((item) => Number(item[metricName] || 0));
        const maxValue = Math.max(...values, 1);
        const graphWidth = width - 2 * padding;
        const graphHeight = height - 2 * padding;
        const step = series.length > 1 ? graphWidth / (series.length - 1) : 0;

        return values.map((value, index) => {
            const x = padding + index * step;
            const normalized = value / maxValue;
            const y = padding + (1 - normalized) * graphHeight;
            return { x, y };
        });
    }

    _pointsToPolyline(points) {
        return points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
    }

    get salesPolyline() {
        return this._pointsToPolyline(this._seriesPoints("sales"));
    }

    get ordersPolyline() {
        return this._pointsToPolyline(this._seriesPoints("orders"));
    }

    get salesAreaPath() {
        const points = this._seriesPoints("sales");
        if (!points.length) {
            return "";
        }
        const baseline = 220 - 20;
        const start = points[0];
        const lines = points.map((point) => `L ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
        const end = points[points.length - 1];
        return `M ${start.x.toFixed(2)} ${baseline.toFixed(2)} ${lines} L ${end.x.toFixed(
            2
        )} ${baseline.toFixed(2)} Z`;
    }
}

registry.category("actions").add("sdlc_magento_dashboard", MagentoDashboard);
