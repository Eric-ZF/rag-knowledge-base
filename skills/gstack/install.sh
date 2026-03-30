#!/bin/bash

# gstack-openclaw 安装脚本
# Usage: ./install.sh

set -e

echo "🦞 安装 gstack-openclaw..."

# 检查 OpenClaw 技能目录
SKILLS_DIR="${OPENCLAW_SKILLS:-$HOME/.openclaw/skills}"

if [ ! -d "$SKILLS_DIR" ]; then
    echo "❌ 错误: 找不到 OpenClaw 技能目录"
    echo "请确保 OpenClaw 已安装，或设置 OPENCLAW_SKILLS 环境变量"
    exit 1
fi

# 安装主技能
echo "📦 安装 gstack 主技能..."
mkdir -p "$SKILLS_DIR/gstack"
cp SKILL.md "$SKILLS_DIR/gstack/"

# 安装子技能
echo "📦 安装子技能..."
for skill in plan-ceo plan-eng review qa ship browse retro office; do
    echo "  - 安装 gstack:$skill"
    mkdir -p "$SKILLS_DIR/gstack-$skill"
    cp "skills/$skill/SKILL.md" "$SKILLS_DIR/gstack-$skill/"
done

# 创建 GSTACK.md 模板
echo "📝 创建 GSTACK.md 模板..."
if [ ! -f "GSTACK.md" ]; then
    cp GSTACK.md.template GSTACK.md 2>/dev/null || true
fi

echo ""
echo "✅ 安装完成！"
echo ""
echo "🚀 使用方法:"
echo "  @gstack:ceo     - CEO / 产品经理模式"
echo "  @gstack:eng     - 工程经理模式"
echo "  @gstack:review  - 代码审查模式"
echo "  @gstack:qa      - QA 模式"
echo "  @gstack:ship    - 发布模式"
echo "  @gstack:browse  - 浏览器测试模式"
echo "  @gstack:retro   - 复盘模式"
echo "  @gstack:office  - 办公室时间模式"
echo ""
echo "💡 提示: 在项目根目录创建 GSTACK.md 记录项目上下文"
echo ""
