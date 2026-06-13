import { defineConfig } from 'vitepress'

const repoName = process.env.GITHUB_REPOSITORY?.split('/')[1] || 'claude-code-orchestrator-skill'
const base = process.env.DOCS_BASE || (process.env.GITHUB_ACTIONS ? `/${repoName}/` : '/')

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
      description: '让 Plus 用出 Pro 的效果',
      themeConfig: {
        nav: [
          { text: '中文入口', link: '/zh/' },
          { text: '英文文档', link: '/guide/getting-started' },
          { text: 'FAQ', link: '/faq' }
        ],
        sidebar: [
          {
            text: '中文',
            items: [
              { text: '入口', link: '/zh/' }
            ]
          },
          {
            text: 'English docs',
            items: [
              { text: 'Get started', link: '/guide/getting-started' },
              { text: 'Prerequisites', link: '/guide/prerequisites' },
              { text: 'MCP', link: '/guide/mcp' },
              { text: 'CLI', link: '/guide/cli' },
              { text: 'Model scoring', link: '/guide/model-scoring' },
              { text: 'Multi-agent strategy', link: '/guide/multi-agent' },
              { text: 'CLAUDE.md', link: '/guide/claude-md' },
              { text: 'FAQ', link: '/faq' }
            ]
          }
        ]
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
      { text: 'FAQ', link: '/faq' },
      { text: '中文', link: '/zh/' }
    ],
    sidebar: [
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
          { text: 'FAQ', link: '/faq' },
          { text: 'Chinese entry', link: '/zh/' }
        ]
      }
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/chu459/claude-code-orchestrator-skill' }
    ],
    footer: {
      message: 'MIT licensed. Not affiliated with OpenAI, Anthropic, Claude, Claude Code, or CCSwitch.',
      copyright: 'Claude Code Orchestrator Skill'
    }
  }
})
