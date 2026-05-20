-- keymaps.lua — additions on top of LazyVim's keymaps. Loaded automatically.

local map = vim.keymap.set

-- Window navigation (also bridges into tmux via vim-tmux-navigator on tmux side).
map("n", "<C-h>", "<C-w>h", { desc = "Window left"  })
map("n", "<C-j>", "<C-w>j", { desc = "Window down"  })
map("n", "<C-k>", "<C-w>k", { desc = "Window up"    })
map("n", "<C-l>", "<C-w>l", { desc = "Window right" })

-- Better up/down on wrapped lines.
map({ "n", "x" }, "j", "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true })
map({ "n", "x" }, "k", "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true })

-- Clear search highlight.
map("n", "<Esc>", "<cmd>nohlsearch<CR>", { desc = "Clear search highlight" })

-- Keep cursor centered on half-page jumps.
map("n", "<C-d>", "<C-d>zz")
map("n", "<C-u>", "<C-u>zz")
