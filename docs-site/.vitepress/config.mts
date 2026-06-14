import { defineConfig } from 'vitepress'

const repoName = process.env.GITHUB_REPOSITORY?.split('/')[1] || 'claude-code-orchestrator-skill'
const base = process.env.DOCS_BASE || (process.env.GITHUB_ACTIONS ? `/${repoName}/` : '/')

const englishSidebar = [
  {
    text: 'Start',
    items: [
      { text: 'Get started', link: '/guide/getting-started' },
      { text: 'Prerequisites', link: '/guide/prerequisites' }
    ]
  },
  {
    text: 'Operate',
    items: [
      { text: 'MCP setup', link: '/guide/mcp' },
      { text: 'CLI reference', link: '/guide/cli' },
      { text: 'Model scoring', link: '/guide/model-scoring' },
      { text: 'Multi-agent strategy', link: '/guide/multi-agent' },
      { text: 'CLAUDE.md', link: '/guide/claude-md' }
    ]
  },
  {
    text: 'Help',
    items: [
      { text: 'Changelog', link: '/changelog' },
      { text: 'FAQ', link: '/faq' }
    ]
  }
]

const chineseSidebar = [
  {
    text: '开始',
    items: [
      { text: '快速开始', link: '/zh/guide/getting-started' },
      { text: '前置条件', link: '/zh/guide/prerequisites' }
    ]
  },
  {
    text: '使用',
    items: [
      { text: 'MCP 设置', link: '/zh/guide/mcp' },
      { text: 'CLI 命令', link: '/zh/guide/cli' },
      { text: '模型评分', link: '/zh/guide/model-scoring' },
      { text: '多 Agent 策略', link: '/zh/guide/multi-agent' },
      { text: 'CLAUDE.md', link: '/zh/guide/claude-md' }
    ]
  },
  {
    text: '帮助',
    items: [
      { text: '更新日志', link: '/zh/changelog' },
      { text: 'FAQ', link: '/zh/faq' }
    ]
  }
]

export default defineConfig({
  title: 'Claude Code Orchestrator',
  description: 'Make Plus feel like Pro.',
  base,
  cleanUrls: true,
  lastUpdated: true,
  head: [
    ['meta', { name: 'theme-color', content: '#0f766e' }],
    ['meta', { property: 'og:title', content: 'Claude Code Orchestrator Skill' }],
    ['meta', { property: 'og:description', content: 'Make Plus feel like Pro.' }]
  ],
  locales: {
    root: {
      label: 'English',
      lang: 'en-US'
    },
    zh: {
      label: '简体中文',
      lang: 'zh-CN',
      title: 'Claude Code Orchestrator',
      description: '让 Plus 用出 Pro 的效果。',
      themeConfig: {
        nav: [
          { text: '指南', link: '/zh/guide/getting-started' },
          { text: 'CLI', link: '/zh/guide/cli' },
          { text: 'MCP', link: '/zh/guide/mcp' },
          { text: '更新日志', link: '/zh/changelog' },
          { text: 'FAQ', link: '/zh/faq' }
        ],
        sidebar: chineseSidebar,
        footer: {
          message: 'MIT 许可。项目与 OpenAI、Anthropic、Claude、Claude Code、CCSwitch 无官方关联。',
          copyright: 'Claude Code Orchestrator Skill'
        },
        outline: {
          label: '本页目录'
        },
        docFooter: {
          prev: '上一页',
          next: '下一页'
        }
      }
    }
  },
  themeConfig: {
    logo: '/mark.svg',
    siteTitle: 'CC Orchestrator',
    search: {
      provider: 'local'
    },
    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'CLI', link: '/guide/cli' },
      { text: 'MCP', link: '/guide/mcp' },
      { text: 'Changelog', link: '/changelog' },
      { text: 'FAQ', link: '/faq' }
    ],
    sidebar: englishSidebar,
    socialLinks: [
      { icon: 'github', link: 'https://github.com/chu459/claude-code-orchestrator-skill' }
    ],
    footer: {
      message: 'MIT licensed. Not affiliated with OpenAI, Anthropic, Claude, Claude Code, or CCSwitch.',
      copyright: 'Claude Code Orchestrator Skill'
    }
  }
})
