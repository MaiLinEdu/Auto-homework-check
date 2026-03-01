FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
# ... 前面的代码不变 ...

# --- 插入下面这一行，使用清华源/国内镜像加速 ---
RUN npm config set registry https://registry.npmmirror.com

# 现在的安装就会非常快了
RUN npm install

# ... 后面的代码不变 ...

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
