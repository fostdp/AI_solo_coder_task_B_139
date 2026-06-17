
class ObjectPool {
    constructor(createFn, resetFn, initialSize = 100) {
        this.createFn = createFn;
        this.resetFn = resetFn;
        this.pool = [];
        this.activeCount = 0;
        
        for (let i = 0; i < initialSize; i++) {
            this.pool.push(this.createFn());
        }
    }

    acquire() {
        let obj;
        if (this.pool.length > 0) {
            obj = this.pool.pop();
        } else {
            obj = this.createFn();
        }
        this.activeCount++;
        return obj;
    }

    release(obj) {
        if (this.resetFn) {
            this.resetFn(obj);
        }
        this.pool.push(obj);
        this.activeCount--;
    }

    releaseAll(activeObjects) {
        for (const obj of activeObjects) {
            this.release(obj);
        }
    }

    getPoolSize() {
        return this.pool.length;
    }

    getActiveCount() {
        return this.activeCount;
    }

    expand(size) {
        for (let i = 0; i < size; i++) {
            this.pool.push(this.createFn());
        }
    }

    clear() {
        this.pool = [];
        this.activeCount = 0;
    }
}

class TrailPointPool extends ObjectPool {
    constructor(initialSize = 5000) {
        super(
            () => ({ x: 0, y: 0 }),
            (p) => { p.x = 0; p.y = 0; },
            initialSize
        );
    }
}

class ParticlePool extends ObjectPool {
    constructor(trailPointPool, initialSize = 500) {
        super(
            () => ({
                x: 0,
                y: 0,
                vx: 0,
                vy: 0,
                life: 0,
                maxLife: 150,
                size: 1,
                trail: [],
                trailLength: 0
            }),
            (p) => {
                p.x = 0;
                p.y = 0;
                p.vx = 0;
                p.vy = 0;
                p.life = 0;
                p.maxLife = 150;
                p.size = 1;
                p.trailLength = 0;
                if (p.trail.length > 0) {
                    trailPointPool.releaseAll(p.trail);
                    p.trail = [];
                }
            },
            initialSize
        );
        this.trailPointPool = trailPointPool;
    }

    acquireTrailPoint() {
        return this.trailPointPool.acquire();
    }

    releaseTrailPoint(point) {
        this.trailPointPool.release(point);
    }
}

class WindFieldVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.width = this.canvas.width;
        this.height = this.canvas.height;
        this.particles = [];
        this.particleCount = 300;
        this.maxTrailLength = 20;
        this.windSpeed = 5;
        this.windDirection = 0;
        this.streamlines = [];
        this.maxStreamlines = 20;
        this.running = false;
        this.animationId = null;
        
        this.noiseOffset = Math.random() * 1000;
        
        this._initPools();
        this._initParticles();
    }

    _initPools() {
        this.trailPointPool = new TrailPointPool(this.particleCount * this.maxTrailLength * 2);
        this.particlePool = new ParticlePool(this.trailPointPool, this.particleCount * 2);
    }

    _initParticles() {
        for (const p of this.particles) {
            this.particlePool.release(p);
        }
        this.particles = [];
        
        for (let i = 0; i < this.particleCount; i++) {
            const p = this.particlePool.acquire();
            this._resetParticle(p, true);
            this.particles.push(p);
        }
    }

    _resetParticle(particle, randomPosition = false) {
        if (randomPosition) {
            particle.x = Math.random() * this.width;
            particle.y = Math.random() * this.height;
        } else {
            particle.x = -10 + Math.random() * 20;
            particle.y = Math.random() * this.height;
        }
        
        particle.vx = 0;
        particle.vy = 0;
        particle.life = Math.random() * 100 + 50;
        particle.maxLife = 150;
        particle.size = Math.random() * 2 + 1;
        particle.trailLength = 0;
        
        for (const tp of particle.trail) {
            this.trailPointPool.release(tp);
        }
        particle.trail = [];
    }

    _addTrailPoint(particle, x, y) {
        if (particle.trailLength >= this.maxTrailLength) {
            const oldest = particle.trail.shift();
            oldest.x = x;
            oldest.y = y;
            particle.trail.push(oldest);
        } else {
            const tp = this.trailPointPool.acquire();
            tp.x = x;
            tp.y = y;
            particle.trail.push(tp);
            particle.trailLength++;
        }
    }

    setParticleCount(count) {
        if (count === this.particleCount) return;
        
        const diff = count - this.particleCount;
        
        if (diff > 0) {
            for (let i = 0; i < diff; i++) {
                const p = this.particlePool.acquire();
                this._resetParticle(p, true);
                this.particles.push(p);
            }
        } else {
            for (let i = 0; i < -diff; i++) {
                const p = this.particles.pop();
                this.particlePool.release(p);
            }
        }
        
        this.particleCount = count;
        
        const neededTrailPoints = this.particleCount * this.maxTrailLength * 2;
        if (this.trailPointPool.getPoolSize() < neededTrailPoints / 2) {
            this.trailPointPool.expand(neededTrailPoints - this.trailPointPool.getPoolSize());
        }
    }

    setWindParams(speed, direction) {
        this.windSpeed = speed;
        this.windDirection = direction * Math.PI / 180;
    }

    getWindVector(x, y, time) {
        const scale = 0.005;
        const nx = x * scale + this.noiseOffset;
        const ny = y * scale + this.noiseOffset;
        
        const turbulence = this.noise(nx * 2, ny * 2, time * 0.0005) * 0.5;
        
        const baseSpeed = this.windSpeed * 0.3;
        const dirX = Math.cos(this.windDirection);
        const dirY = Math.sin(this.windDirection);
        
        const vortexX = Math.sin(ny * 3 + time * 0.001) * 0.3;
        const vortexY = Math.cos(nx * 3 + time * 0.001) * 0.3;
        
        return {
            x: dirX * baseSpeed + vortexX + turbulence * dirX,
            y: dirY * baseSpeed + vortexY + turbulence * dirY
        };
    }

    noise(x, y, z) {
        const p = [151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180];
        const perm = new Array(512);
        for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
        
        const X = Math.floor(x) & 255;
        const Y = Math.floor(y) & 255;
        const Z = Math.floor(z) & 255;
        
        x -= Math.floor(x);
        y -= Math.floor(y);
        z -= Math.floor(z);
        
        const u = this.fade(x);
        const v = this.fade(y);
        const w = this.fade(z);
        
        const A = perm[X] + Y;
        const AA = perm[A] + Z;
        const AB = perm[A + 1] + Z;
        const B = perm[X + 1] + Y;
        const BA = perm[B] + Z;
        const BB = perm[B + 1] + Z;
        
        return this.lerp(w, this.lerp(v, this.lerp(u, this.grad(perm[AA], x, y, z), this.grad(perm[BA], x - 1, y, z)), this.lerp(u, this.grad(perm[AB], x, y - 1, z), this.grad(perm[BB], x - 1, y - 1, z))), this.lerp(v, this.lerp(u, this.grad(perm[AA + 1], x, y, z - 1), this.grad(perm[BA + 1], x - 1, y, z - 1)), this.lerp(u, this.grad(perm[AB + 1], x, y - 1, z - 1), this.grad(perm[BB + 1], x - 1, y - 1, z - 1))));
    }

    fade(t) {
        return t * t * t * (t * (t * 6 - 15) + 10);
    }

    lerp(t, a, b) {
        return a + t * (b - a);
    }

    grad(hash, x, y, z) {
        const h = hash & 15;
        const u = h < 8 ? x : y;
        const v = h < 4 ? y : h === 12 || h === 14 ? x : z;
        return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
    }

    getSpeedColor(speed) {
        const normalizedSpeed = Math.min(speed / 15, 1);
        const hue = 240 - normalizedSpeed * 240;
        return `hsla(${hue}, 100%, 50%, 0.8)`;
    }

    update(time) {
        for (const particle of this.particles) {
            const wind = this.getWindVector(particle.x, particle.y, time);
            particle.vx = wind.x * this.windSpeed * 0.5;
            particle.vy = wind.y * this.windSpeed * 0.5;
            
            this._addTrailPoint(particle, particle.x, particle.y);
            
            particle.x += particle.vx;
            particle.y += particle.vy;
            particle.life--;
            
            let needReset = false;
            if (particle.x < -10) {
                particle.x = this.width + 10;
                needReset = true;
            } else if (particle.x > this.width + 10) {
                particle.x = -10;
                needReset = true;
            }
            if (particle.y < -10) {
                particle.y = this.height + 10;
                needReset = true;
            } else if (particle.y > this.height + 10) {
                particle.y = -10;
                needReset = true;
            }
            
            if (particle.life <= 0 || needReset) {
                if (particle.life <= 0) {
                    particle.x = Math.random() * this.width;
                    particle.y = Math.random() * this.height;
                }
                particle.life = particle.maxLife;
                particle.trailLength = 0;
                for (const tp of particle.trail) {
                    this.trailPointPool.release(tp);
                }
                particle.trail = [];
            }
        }
    }

    draw() {
        this.ctx.fillStyle = 'rgba(15, 23, 42, 0.15)';
        this.ctx.fillRect(0, 0, this.width, this.height);
        
        for (const particle of this.particles) {
            if (particle.trailLength < 2) continue;
            
            const speed = Math.sqrt(particle.vx * particle.vx + particle.vy * particle.vy);
            const alpha = particle.life / particle.maxLife;
            
            this.ctx.beginPath();
            this.ctx.moveTo(particle.trail[0].x, particle.trail[0].y);
            for (let i = 1; i < particle.trailLength; i++) {
                this.ctx.lineTo(particle.trail[i].x, particle.trail[i].y);
            }
            this.ctx.strokeStyle = `hsla(${180 + speed * 10}, 80%, 60%, ${alpha * 0.6})`;
            this.ctx.lineWidth = particle.size * 0.8;
            this.ctx.lineCap = 'round';
            this.ctx.stroke();
            
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            this.ctx.fillStyle = `hsla(${180 + speed * 10}, 100%, 70%, ${alpha})`;
            this.ctx.fill();
        }
        
        this.drawWindIndicator();
    }

    drawWindIndicator() {
        const cx = 60;
        const cy = 60;
        const radius = 40;
        
        this.ctx.beginPath();
        this.ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        this.ctx.strokeStyle = 'rgba(148, 163, 184, 0.5)';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
        
        for (let i = 0; i < 8; i++) {
            const angle = (i * 45) * Math.PI / 180;
            const x1 = cx + Math.cos(angle) * (radius - 5);
            const y1 = cy + Math.sin(angle) * (radius - 5);
            const x2 = cx + Math.cos(angle) * (radius + 5);
            const y2 = cy + Math.sin(angle) * (radius + 5);
            this.ctx.beginPath();
            this.ctx.moveTo(x1, y1);
            this.ctx.lineTo(x2, y2);
            this.ctx.strokeStyle = 'rgba(148, 163, 184, 0.5)';
            this.ctx.lineWidth = 1;
            this.ctx.stroke();
            
            const labelX = cx + Math.cos(angle) * (radius + 15);
            const labelY = cy + Math.sin(angle) * (radius + 15);
            this.ctx.fillStyle = 'rgba(148, 163, 184, 0.8)';
            this.ctx.font = '10px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            const directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北'];
            this.ctx.fillText(directions[i], labelX, labelY);
        }
        
        const arrowLength = radius * 0.7;
        const arrowX = cx + Math.cos(this.windDirection) * arrowLength;
        const arrowY = cy + Math.sin(this.windDirection) * arrowLength;
        
        this.ctx.beginPath();
        this.ctx.moveTo(cx, cy);
        this.ctx.lineTo(arrowX, arrowY);
        this.ctx.strokeStyle = '#f97316';
        this.ctx.lineWidth = 3;
        this.ctx.lineCap = 'round';
        this.ctx.stroke();
        
        const headLength = 8;
        const headAngle = Math.PI / 6;
        this.ctx.beginPath();
        this.ctx.moveTo(arrowX, arrowY);
        this.ctx.lineTo(
            arrowX - headLength * Math.cos(this.windDirection - headAngle),
            arrowY - headLength * Math.sin(this.windDirection - headAngle)
        );
        this.ctx.moveTo(arrowX, arrowY);
        this.ctx.lineTo(
            arrowX - headLength * Math.cos(this.windDirection + headAngle),
            arrowY - headLength * Math.sin(this.windDirection + headAngle)
        );
        this.ctx.strokeStyle = '#f97316';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
        
        this.ctx.fillStyle = '#f8fafc';
        this.ctx.font = 'bold 14px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(`${this.windSpeed.toFixed(1)} m/s`, cx, cy + radius + 30);
        this.ctx.font = '11px Arial';
        this.ctx.fillStyle = 'rgba(148, 163, 184, 0.8)';
        this.ctx.fillText('风速风向', cx, cy + radius + 45);
    }

    generateStreamlines(windFieldData) {
        this.streamlines = [];
        const gridSize = windFieldData.grid_size;
        const bounds = windFieldData.bounds;
        
        const startPoints = [];
        for (let i = 0; i < this.maxStreamlines; i++) {
            startPoints.push({
                x: bounds.min_x + Math.random() * (bounds.max_x - bounds.min_x),
                y: bounds.min_y + Math.random() * (bounds.max_y - bounds.min_y),
                z: bounds.min_z + Math.random() * (bounds.max_z - bounds.min_z)
            });
        }
        
        for (const start of startPoints) {
            const streamline = {
                points: [start],
                speed: []
            };
            
            let current = { ...start };
            const stepSize = 0.5;
            const maxSteps = 100;
            
            for (let i = 0; i < maxSteps; i++) {
                const gx = Math.floor((current.x - bounds.min_x) / (bounds.max_x - bounds.min_x) * (gridSize - 1));
                const gy = Math.floor((current.y - bounds.min_y) / (bounds.max_y - bounds.min_y) * (gridSize - 1));
                const gz = Math.floor((current.z - bounds.min_z) / (bounds.max_z - bounds.min_z) * (gridSize - 1));
                
                if (gx < 0 || gx >= gridSize || gy < 0 || gy >= gridSize || gz < 0 || gz >= gridSize) break;
                
                const idx = gz * gridSize * gridSize + gy * gridSize + gx;
                if (idx >= windFieldData.velocities.length) break;
                
                const vel = windFieldData.velocities[idx];
                const speed = Math.sqrt(vel.u * vel.u + vel.v * vel.v + vel.w * vel.w);
                
                if (speed < 0.01) break;
                
                streamline.speed.push(speed);
                
                current = {
                    x: current.x + vel.u * stepSize / speed,
                    y: current.y + vel.v * stepSize / speed,
                    z: current.z + vel.w * stepSize / speed
                };
                
                streamline.points.push({ ...current });
            }
            
            if (streamline.points.length > 5) {
                this.streamlines.push(streamline);
            }
        }
        
        return this.streamlines;
    }

    async loadWindFieldData(segmentId, startTime, endTime) {
        try {
            const params = new URLSearchParams({
                segment_id: segmentId,
                start_time: startTime,
                end_time: endTime,
                grid_size: 20
            });
            
            const response = await fetch(`/api/wind-field/streamlines?${params}`);
            const data = await response.json();
            return this.generateStreamlines(data);
        } catch (error) {
            console.error('加载风场数据失败:', error);
            return [];
        }
    }

    start() {
        if (this.running) return;
        this.running = true;
        this.animate();
    }

    stop() {
        this.running = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    animate(time = 0) {
        if (!this.running) return;
        this.update(time);
        this.draw();
        this.animationId = requestAnimationFrame((t) => this.animate(t));
    }

    resize(width, height) {
        this.width = width;
        this.height = height;
        this.canvas.width = width;
        this.canvas.height = height;
        
        for (const p of this.particles) {
            this._resetParticle(p, true);
        }
    }

    getMemoryStats() {
        return {
            particlePoolSize: this.particlePool.getPoolSize(),
            activeParticles: this.particleCount,
            trailPointPoolSize: this.trailPointPool.getPoolSize(),
            activeTrailPoints: this.particleCount * this.maxTrailLength,
            totalPoolObjects: this.particlePool.getPoolSize() + this.trailPointPool.getPoolSize()
        };
    }

    destroy() {
        this.stop();
        for (const p of this.particles) {
            this.particlePool.release(p);
        }
        this.particles = [];
        this.particlePool.clear();
        this.trailPointPool.clear();
    }
}

class WindField3D {
    constructor(scene) {
        this.scene = scene;
        this.streamlineObjects = [];
        this.particleSystems = [];
        this.windData = null;
        this.geometryPool = [];
        this.materialPool = [];
        this.maxPoolSize = 30;
    }

    _acquireGeometry(type, ...args) {
        let geometry = null;
        
        for (let i = 0; i < this.geometryPool.length; i++) {
            if (this.geometryPool[i].type === type) {
                geometry = this.geometryPool.splice(i, 1)[0].geo;
                break;
            }
        }
        
        if (!geometry) {
            if (type === 'tube') {
                const [curve, tubularSegments, radius, radialSegments, closed] = args;
                geometry = new THREE.TubeGeometry(curve, tubularSegments, radius, radialSegments, closed);
            } else if (type === 'points') {
                geometry = new THREE.BufferGeometry();
            }
        }
        
        return geometry;
    }

    _releaseGeometry(geometry, type) {
        if (this.geometryPool.length < this.maxPoolSize) {
            this.geometryPool.push({ geo: geometry, type: type });
        } else {
            geometry.dispose();
        }
    }

    _acquireMaterial(type) {
        let material = null;
        
        for (let i = 0; i < this.materialPool.length; i++) {
            if (this.materialPool[i].type === type) {
                material = this.materialPool.splice(i, 1)[0].mat;
                break;
            }
        }
        
        if (!material) {
            if (type === 'tube') {
                material = new THREE.MeshBasicMaterial({
                    vertexColors: true,
                    transparent: true,
                    opacity: 0.7
                });
            } else if (type === 'points') {
                material = new THREE.PointsMaterial({
                    size: 0.15,
                    vertexColors: true,
                    transparent: true,
                    opacity: 0.9,
                    blending: THREE.AdditiveBlending
                });
            }
        }
        
        return material;
    }

    _releaseMaterial(material, type) {
        if (this.materialPool.length < this.maxPoolSize) {
            this.materialPool.push({ mat: material, type: type });
        } else {
            material.dispose();
        }
    }

    createStreamlineGeometry(streamline, colorMap = true) {
        const points = [];
        const colors = [];
        
        for (let i = 0; i < streamline.points.length; i++) {
            const p = streamline.points[i];
            points.push(new THREE.Vector3(p.x, p.y, p.z));
            
            if (colorMap && i < streamline.speed.length) {
                const speed = streamline.speed[i];
                const normalizedSpeed = Math.min(speed / 10, 1);
                const hue = 0.7 - normalizedSpeed * 0.7;
                const color = new THREE.Color().setHSL(hue, 1, 0.5);
                colors.push(color.r, color.g, color.b);
            } else {
                colors.push(0, 0.7, 1);
            }
        }
        
        const curve = new THREE.CatmullRomCurve3(points);
        const geometry = this._acquireGeometry('tube', curve, 64, 0.03, 8, false);
        
        const colorAttribute = new THREE.Float32BufferAttribute(colors, 3);
        geometry.setAttribute('color', colorAttribute);
        
        const material = this._acquireMaterial('tube');
        
        return new THREE.Mesh(geometry, material);
    }

    createParticleSystem(streamline, particleCount = 20) {
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        const offsets = new Float32Array(particleCount);
        
        for (let i = 0; i < particleCount; i++) {
            const t = i / particleCount;
            const idx = Math.floor(t * (streamline.points.length - 1));
            const p = streamline.points[idx];
            
            positions[i * 3] = p.x;
            positions[i * 3 + 1] = p.y;
            positions[i * 3 + 2] = p.z;
            
            const speed = streamline.speed[Math.min(idx, streamline.speed.length - 1)] || 1;
            const normalizedSpeed = Math.min(speed / 10, 1);
            const hue = 0.7 - normalizedSpeed * 0.7;
            const color = new THREE.Color().setHSL(hue, 1, 0.6);
            
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
            
            offsets[i] = Math.random() * streamline.points.length;
        }
        
        const geometry = this._acquireGeometry('points');
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.setAttribute('offset', new THREE.BufferAttribute(offsets, 1));
        
        const material = this._acquireMaterial('points');
        
        return {
            points: new THREE.Points(geometry, material),
            streamline: streamline,
            particleCount: particleCount
        };
    }

    async updateWindField(segmentId, startTime, endTime) {
        try {
            this.clear();
            
            const params = new URLSearchParams({
                segment_id: segmentId,
                start_time: startTime,
                end_time: endTime,
                grid_size: 20
            });
            
            const response = await fetch(`/api/wind-field/streamlines?${params}`);
            this.windData = await response.json();
            
            for (const streamline of this.windData.streamlines || []) {
                if (streamline.points.length > 5) {
                    const tube = this.createStreamlineGeometry(streamline);
                    this.streamlineObjects.push(tube);
                    this.scene.add(tube);
                    
                    const particleSys = this.createParticleSystem(streamline);
                    this.particleSystems.push(particleSys);
                    this.scene.add(particleSys.points);
                }
            }
            
            return this.streamlineObjects.length;
        } catch (error) {
            console.error('更新3D风场失败:', error);
            return 0;
        }
    }

    animate(time) {
        for (const sys of this.particleSystems) {
            const positions = sys.points.geometry.attributes.position.array;
            
            for (let i = 0; i < sys.particleCount; i++) {
                const offset = (time * 0.001 + i * 0.2) % sys.streamline.points.length;
                const idx = Math.floor(offset);
                const t = offset - idx;
                
                if (idx < sys.streamline.points.length - 1) {
                    const p1 = sys.streamline.points[idx];
                    const p2 = sys.streamline.points[idx + 1];
                    
                    positions[i * 3] = p1.x + (p2.x - p1.x) * t;
                    positions[i * 3 + 1] = p1.y + (p2.y - p1.y) * t;
                    positions[i * 3 + 2] = p1.z + (p2.z - p1.z) * t;
                }
            }
            
            sys.points.geometry.attributes.position.needsUpdate = true;
        }
    }

    clear() {
        for (const obj of this.streamlineObjects) {
            this.scene.remove(obj);
            this._releaseGeometry(obj.geometry, 'tube');
            this._releaseMaterial(obj.material, 'tube');
        }
        this.streamlineObjects = [];
        
        for (const sys of this.particleSystems) {
            this.scene.remove(sys.points);
            this._releaseGeometry(sys.points.geometry, 'points');
            this._releaseMaterial(sys.points.material, 'points');
        }
        this.particleSystems = [];
    }

    getPoolStats() {
        return {
            geometryPoolSize: this.geometryPool.length,
            materialPoolSize: this.materialPool.length,
            activeStreamlines: this.streamlineObjects.length,
            activeParticleSystems: this.particleSystems.length
        };
    }

    destroy() {
        this.clear();
        
        for (const item of this.geometryPool) {
            item.geo.dispose();
        }
        this.geometryPool = [];
        
        for (const item of this.materialPool) {
            item.mat.dispose();
        }
        this.materialPool = [];
    }
}
